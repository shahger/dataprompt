import markImg from '../assets/forte_mark.png';

export function SiteFooter({ onReset, canReset }: { onReset: () => void; canReset: boolean }) {
  return (
    <footer className="site-footer">
      <div className="container">
        <div className="footer__top">
          <div className="footer__brand">
            <span className="logo-tile logo-tile--sm">
              <img src={markImg} alt="" />
            </span>
            <div>
              <b>ForteBank · Datathon 26</b>
              <span>AI-сервис выявления нарушений кассовой дисциплины по видеозаписям</span>
            </div>
          </div>
          {canReset && (
            <button type="button" className="footer__reset" onClick={onReset}>
              Сбросить и начать заново
            </button>
          )}
        </div>
        <hr />
        <p className="footer__legal">
          Результат анализа — подсказка для проверки человеком, а не окончательное юридическое или дисциплинарное заключение. Сервис
          анализирует только видеоряд, звук не используется, лица не идентифицируются.
        </p>
      </div>
    </footer>
  );
}
