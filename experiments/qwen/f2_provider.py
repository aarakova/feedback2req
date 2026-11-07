"""Test-only explicit live provider for unchanged F2 execute_grouping.

No production import/registration. Caller must seed only synthetic application
data, authorize the runtime and pin identity before preparing the F2 attempt.
"""

import hashlib
from copy import deepcopy

from ai.group_findings.validation import GroupingError

from .adapter import ADAPTER_VERSION, config_check, sha
from .portable import F2_COMMIT
from .run import bounded_execute, bounded_identity, output_path, write


class F2LocalProvider:
    name = "qwen_local_experiment"
    synthetic = False

    def __init__(self, cfg, lock, output, *, approved=False, synthetic_data=False):
        if approved is not True or synthetic_data is not True:
            raise GroupingError(
                "provider_error", "explicit_local_synthetic_opt_in_required"
            )
        self.cfg = deepcopy(config_check(cfg))
        if self.cfg["timeout_seconds"] > 90:
            raise GroupingError("provider_error", "f2_deadline_budget")
        if bounded_identity(self.cfg) != lock:
            raise GroupingError("provider_error", "lock_mismatch")
        self.model = self.cfg["model"]
        self.lock = deepcopy(lock)
        self.output = output_path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.called = False
        write(
            self.output / "metadata.json",
            {
                "mode": "real_local_inference_f2_test",
                "synthetic_data": True,
                "runtime": self.lock,
                "configuration": self.cfg,
                "adapter_version": ADAPTER_VERSION,
                "f2_reference_commit": F2_COMMIT,
            },
        )

    def group(self, request):
        if self.called:
            raise GroupingError("provider_error", "single_attempt_provider")
        self.called = True
        # Preserve trusted F2 request exactly; never rewrite source/state IDs.
        write(self.output / "request.json", request)
        result = bounded_execute(self.cfg, request)
        raw = result.pop("raw", None)
        content = result.pop("content", None)
        result.pop("candidate", None)
        result["request_sha256"] = sha(request)
        result["response_sha256"] = (
            hashlib.sha256(content.encode("utf-8", errors="surrogatepass")).hexdigest()
            if content is not None
            else None
        )
        if raw is not None:
            with (self.output / "response.envelope.bin").open("xb") as stream:
                stream.write(raw)
        if content is not None:
            with (self.output / "response.json").open("xb") as stream:
                stream.write(content.encode("utf-8", errors="surrogatepass"))
        write(self.output / "diagnostics.json", result)
        if result["error"]:
            if result["request_attempted"] is False:
                # F2 maps this pre-call failure to ai_performed=False. Preserve
                # the exact local reason in diagnostics, outside canonical JSON.
                raise GroupingError("provider_error", "provider_not_configured")
            if (
                result.get("provider_completed")
                and content is not None
                and result["error"]["code"] == "invalid_response"
            ):
                # Let the unchanged component reject canonical JSON/refs in its
                # validation stage, not misclassify that failure as transport.
                return content
            code = result["error"]["code"]
            rule = {
                "invalid_response": "provider_envelope",
                "timeout": "provider_timeout",
            }.get(code, "provider_transport")
            raise GroupingError(
                code if code in {"invalid_response", "timeout"} else "provider_error",
                rule,
            )
        return content
