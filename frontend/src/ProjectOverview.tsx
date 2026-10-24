import type { Project } from './api';
import { Permissions } from './ui';
import { projectHref, sectionNames } from './routes';
import type { ProjectSection } from './routes';

export function ProjectOverview({ project }: { project: Project }) {
  return <div className="project-overview stack">
    <div className="overview-heading"><p className="eyebrow">Рабочая область</p><h2>Обзор проекта</h2>
      <p className="muted">Материалы продукта и доступные действия в одном месте.</p></div>
    <section className="capability-grid" aria-label="Возможности проекта">
      <article className="panel capability"><p className="eyebrow">Обратная связь</p><h3>Текстовые отзывы</h3>
        <p className="capability-state">Доступно</p><p className="muted small">Добавление и просмотр полного текста.</p></article>
      <article className="panel capability"><p className="eyebrow">Контекст продукта</p><h3>Документация</h3>
        <p className="capability-state">Доступно</p><p className="muted small">Документы хранятся отдельно от отзывов.</p></article>
      <article className="panel capability future-capability"><p className="eyebrow">Анализ</p><h3>Обработка и результаты</h3>
        <p className="capability-state">Не подключено</p><p className="muted small">Находки и требования появятся после подключения анализа.</p></article>
    </section>
    <div className="overview-columns">
      <section className="panel overview-panel stack" aria-labelledby="overview-actions">
        <h3 id="overview-actions">С чего начать</h3>
        <p className="muted">Добавьте текстовую обратную связь и описание текущего продукта.
          В разделе материалов можно открыть сохранённые тексты и продолжить работу.</p>
        <a className="primary action-link" href={projectHref(project.id, 'materials')}>Открыть материалы <span aria-hidden="true">→</span></a>
        {project.permissions.is_owner && <a className="secondary action-link" href={projectHref(project.id, 'access')}>Управлять доступом</a>}
        <p className="muted small">Добавление материала сохраняет текст. Обработка автоматически не запускается.</p>
      </section>
      <section className="panel overview-panel stack" aria-labelledby="overview-permissions">
        <h3 id="overview-permissions">Ваши полномочия</h3><Permissions project={project} />
        <p className="muted">{project.permissions.is_owner ? 'Вы — владелец этого проекта с правами участника и утверждения.'
          : project.permissions.can_approve ? 'Вы — участник с дополнительным правом утверждения.' : 'Вы — участник этого проекта.'}</p>
        <dl><dt>Идентификатор проекта</dt><dd className="mono">{project.id}</dd></dl>
      </section>
    </div>
    <p className="overview-note">Обзор показывает доступные возможности. Количественные показатели материалов,
      находок и требований пока не представлены.</p>
  </div>;
}

export function FutureSection({ projectId, section }: {
  projectId: string; section: Extract<ProjectSection, 'findings' | 'requirements' | 'processing'>;
}) {
  const descriptions = {
    findings: 'Здесь будут находки и группы обратной связи с переходами к исходным основаниям.',
    requirements: 'Здесь будут проекты требований, их основания, результаты проверки и решения человека.',
    processing: 'Здесь будут запуск анализа, фактические состояния этапов и доступные действия при ошибках.',
  };
  return <section className="panel future-section stack" aria-labelledby="future-heading">
    <p className="eyebrow">Следующие возможности</p><h2 id="future-heading">{sectionNames[section]}</h2>
    <span className="badge">Функция не подключена</span><p>{descriptions[section]}</p>
    <p className="muted">Этот раздел пока недоступен для работы. Результаты анализа здесь пока не отображаются.</p>
    <a className="secondary action-link" href={projectHref(projectId, 'materials')}>Перейти к материалам</a>
  </section>;
}
