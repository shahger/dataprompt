import { Icon, type IconName } from './Icon';

interface Item {
  icon: IconName;
  title: string;
  text: string;
  filled?: boolean;
}

const ITEMS: Item[] = [
  {
    icon: 'shield',
    title: 'Локальная обработка',
    text: 'Все модели работают внутри контура банка. Видео, кадры и описания не уходят в облачные AI-сервисы.',
    filled: true,
  },
  {
    icon: 'link',
    title: 'Нормативная база',
    text: 'Каждое событие сопоставляется с правилом и документом: акты НБРК и adilet.zan.kz, с указанием пункта.',
  },
  {
    icon: 'check',
    title: 'Решение за человеком',
    text: 'Результат — подсказка для проверки: кадр, время и обоснование. Это не юридическое и не дисциплинарное заключение.',
  },
];

export function InfoCards() {
  return (
    <section className="trust">
      <div className="container">
        <h2 className="section-title section-title--deep">Безопасность и доверие</h2>
        <p className="section-sub">Принципы работы сервиса анализа видеозаписей кассовой зоны.</p>
        <div className="trust__grid">
          {ITEMS.map((it) => (
            <article key={it.title} className={`trust__card ${it.filled ? 'is-filled' : ''}`}>
              <span className="trust__icon">
                <Icon name={it.icon} size={22} />
              </span>
              <h3>{it.title}</h3>
              <p>{it.text}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
