
import { useState } from 'react'
import {
  ArrowRight,
  BookOpenCheck,
  Building2,
  CheckCircle2,
  ChevronRight,
  FileCheck2,
  Fingerprint,
  GraduationCap,
  LockKeyhole,
  Menu,
  ScanSearch,
  ShieldCheck,
  UploadCloud,
  X,
} from 'lucide-react'
import {
  Link,
  Navigate,
  Route,
  Routes,
} from 'react-router-dom'
import './App.css'

import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import AdminPage from './pages/AdminPage'
import { useAuth } from './context/AuthContext'

const features = [
  {
    icon: Fingerprint,
    title: 'Фиксация авторства',
    description:
      'Регистрируйте материалы и получайте уникальный регистрационный номер для каждого документа.',
  },
  {
    icon: ScanSearch,
    title: 'Проверка уникальности',
    description:
      'Автоматический анализ текста, поиск совпадений и формирование результата проверки.',
  },
  {
    icon: FileCheck2,
    title: 'Подтверждение регистрации',
    description:
      'Храните сведения о зарегистрированных материалах и связанных с ними сертификатах.',
  },
]

const audiences = [
  {
    icon: BookOpenCheck,
    title: 'Авторам',
    description:
      'Регистрируйте научные работы, статьи, учебные материалы и другие авторские произведения.',
    link: 'Зарегистрировать материал',
  },
  {
    icon: GraduationCap,
    title: 'Экспертам',
    description:
      'Работайте с результатами проверок, анализируйте совпадения и рассматривайте обращения.',
    link: 'Рабочее пространство эксперта',
  },
  {
    icon: Building2,
    title: 'Организациям',
    description:
      'Создайте единое пространство для учёта материалов и контроля интеллектуальных ресурсов.',
    link: 'Возможности для организаций',
  },
]

function HomePage() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { user } = useAuth()

  const closeMenu = () => setMenuOpen(false)

  return (
    <div className="site-shell">
      <header className="header">
        <div className="container header-inner">
          <Link className="brand" to="/" onClick={closeMenu}>
            <span className="brand-icon">
              <ShieldCheck size={23} strokeWidth={2.2} />
            </span>
            <span className="brand-name">
              Автор<span>Реестр</span>
            </span>
          </Link>

          <button
            className="mobile-menu-button"
            type="button"
            aria-label={menuOpen ? 'Закрыть меню' : 'Открыть меню'}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? <X size={23} /> : <Menu size={23} />}
          </button>

          <nav className={`navigation ${menuOpen ? 'navigation-open' : ''}`}>
            <a href="#features" onClick={closeMenu}>Возможности</a>
            <a href="#audience" onClick={closeMenu}>Кому подходит</a>
            <a href="#how-it-works" onClick={closeMenu}>Как это работает</a>
            <div className="mobile-nav-actions">
              {user ? (
  <>
    {user.role === 'admin' && (
      <Link className="button button-outline" to="/admin" onClick={closeMenu}>
        Админ-панель
      </Link>
    )}
    <Link className="button button-primary" to="/dashboard" onClick={closeMenu}>
      Личный кабинет <ArrowRight size={16} />
    </Link>
  </>
) : (
                <>
                  <Link className="button button-outline" to="/login" onClick={closeMenu}>
                    Войти
                  </Link>
                  <Link className="button button-primary" to="/register" onClick={closeMenu}>
                    Начать работу <ArrowRight size={16} />
                  </Link>
                </>
              )}
            </div>
          </nav>

          <div className="header-actions">
            {user ? (
  <>
    {user.role === 'admin' && (
      <Link className="button button-outline button-small" to="/admin">
        Админ-панель
      </Link>
    )}
    <Link className="button button-primary button-small" to="/dashboard">
      Личный кабинет <ArrowRight size={16} />
    </Link>
  </>
) : (
              <>
                <Link className="button button-text" to="/login">Войти</Link>
                <Link className="button button-primary button-small" to="/register">
                  Регистрация <ArrowRight size={16} />
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main>
        <section className="hero" id="home">
          <div className="container hero-grid">
            <div className="hero-content">
              <div className="eyebrow">
                <span className="eyebrow-dot" />
                Цифровой реестр авторских материалов
              </div>

              <h1>
                Ваши идеи.
                <br />
                Ваше <span className="accent-text">авторство.</span>
                <br />
                Под защитой.
              </h1>

              <p className="hero-description">
                Единое пространство для регистрации интеллектуальных
                материалов, проверки уникальности и подтверждения авторства.
              </p>

              <div className="hero-actions">
                <Link className="button button-primary button-large" to={user ? '/dashboard' : '/register'}>
                  Зарегистрировать материал
                  <ArrowRight size={18} />
                </Link>
                <a className="button button-outline button-large" href="#how-it-works">
                  Узнать больше
                </a>
              </div>

              <div className="hero-note">
                <LockKeyhole size={16} />
                <span>Персональный доступ и централизованное хранение данных</span>
              </div>
            </div>

            <div className="hero-visual">
              <div className="visual-glow" />
              <div className="document-card">
                <div className="document-top">
                  <div className="document-brand">
                    <span className="mini-brand-icon">
                      <ShieldCheck size={17} />
                    </span>
                    <span>АвторРеестр</span>
                  </div>
                  <span className="document-label">ПРИМЕР ИНТЕРФЕЙСА</span>
                </div>

                <div className="document-icon">
                  <FileCheck2 size={30} />
                </div>

                <div className="document-title">Карточка материала</div>
                <div className="document-subtitle">
                  Сведения о зарегистрированном документе
                </div>

                <div className="document-divider" />

                <div className="document-field">
                  <span>Регистрационный номер</span>
                  <strong>RM-2026-000001</strong>
                </div>
                <div className="document-field">
                  <span>Тип документа</span>
                  <strong>Авторский материал</strong>
                </div>
                <div className="document-field">
                  <span>Статус обработки</span>
                  <strong className="status-complete">
                    <CheckCircle2 size={15} /> Завершена
                  </strong>
                </div>

                <div className="uniqueness-panel">
                  <div>
                    <span className="uniqueness-caption">
                      Пример результата проверки
                    </span>
                    <strong className="uniqueness-value">100%</strong>
                    <span className="uniqueness-label">
                      Уникальность материала
                    </span>
                  </div>
                  <div className="progress-ring">
                    <CheckCircle2 size={31} />
                  </div>
                </div>
              </div>

              <div className="floating-card">
                <span className="floating-icon"><Fingerprint size={19} /></span>
                <span>
                  <strong>Цифровой учёт</strong>
                  <small>Каждому материалу — свой номер</small>
                </span>
              </div>
              <div className="visual-decoration visual-decoration-one" />
              <div className="visual-decoration visual-decoration-two" />
            </div>
          </div>
        </section>

        <section className="trust-strip">
          <div className="container trust-inner">
            <div className="trust-item">
              <Fingerprint size={21} />
              <span>Регистрация материалов</span>
            </div>
            <div className="trust-item">
              <ScanSearch size={21} />
              <span>Анализ уникальности</span>
            </div>
            <div className="trust-item">
              <LockKeyhole size={21} />
              <span>Контроль доступа</span>
            </div>
            <div className="trust-item">
              <FileCheck2 size={21} />
              <span>Учёт сертификатов</span>
            </div>
          </div>
        </section>

        <section className="section features-section" id="features">
          <div className="container">
            <div className="section-heading">
              <span className="section-kicker">ВОЗМОЖНОСТИ ПЛАТФОРМЫ</span>
              <h2>Всё необходимое для работы с авторскими материалами</h2>
              <p>
                От регистрации документа до анализа его уникальности —
                основные процессы в одной системе.
              </p>
            </div>

            <div className="feature-grid">
              {features.map((feature) => {
                const Icon = feature.icon
                return (
                  <article className="feature-card" key={feature.title}>
                    <div className="feature-icon">
                      <Icon size={25} />
                    </div>
                    <h3>{feature.title}</h3>
                    <p>{feature.description}</p>
                    <a href="#how-it-works" className="card-link">
                      Подробнее <ChevronRight size={17} />
                    </a>
                  </article>
                )
              })}
            </div>
          </div>
        </section>

        <section className="section audience-section" id="audience">
          <div className="container">
            <div className="section-heading">
              <span className="section-kicker">ЕДИНАЯ ПЛАТФОРМА</span>
              <h2>Решение для разных задач</h2>
              <p>
                У каждого участника свой сценарий работы и необходимые
                инструменты.
              </p>
            </div>

            <div className="audience-grid">
              {audiences.map((item) => {
                const Icon = item.icon
                return (
                  <article className="audience-card" key={item.title}>
                    <div className="audience-icon">
                      <Icon size={27} />
                    </div>
                    <h3>{item.title}</h3>
                    <p>{item.description}</p>
                    <Link to="/register" className="card-link">
                      {item.link} <ArrowRight size={16} />
                    </Link>
                  </article>
                )
              })}
            </div>
          </div>
        </section>

        <section className="section process-section" id="how-it-works">
          <div className="container process-grid">
            <div className="process-heading">
              <span className="section-kicker">ПРОСТОЙ ПРОЦЕСС</span>
              <h2>От загрузки до результата — несколько шагов</h2>
              <p>
                Платформа сопровождает материал на основных этапах
                регистрации и проверки.
              </p>
              <Link to="/register" className="button button-primary">
                Попробовать платформу <ArrowRight size={17} />
              </Link>
            </div>

            <div className="steps-list">
              <div className="step-item">
                <span className="step-number">01</span>
                <div>
                  <h3>Создайте аккаунт</h3>
                  <p>Зарегистрируйтесь и получите доступ к личному кабинету.</p>
                </div>
              </div>
              <div className="step-item">
                <span className="step-number">02</span>
                <div>
                  <h3>Загрузите материал</h3>
                  <p>Добавьте документ и заполните сведения о нём.</p>
                </div>
              </div>
              <div className="step-item">
                <span className="step-number">03</span>
                <div>
                  <h3>Дождитесь обработки</h3>
                  <p>Система извлечёт текст и выполнит анализ совпадений.</p>
                </div>
              </div>
              <div className="step-item">
                <span className="step-number">04</span>
                <div>
                  <h3>Получите результат</h3>
                  <p>Просмотрите статус, оценку уникальности и сведения о регистрации.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="cta-section">
          <div className="container cta-inner">
            <div className="cta-icon"><UploadCloud size={28} /></div>
            <h2>Начните работать с авторскими материалами</h2>
            <p>
              Создайте аккаунт, чтобы зарегистрировать первый материал
              и отслеживать его обработку.
            </p>
            <Link className="button button-white button-large" to={user ? '/dashboard' : '/register'}>
              Перейти к регистрации <ArrowRight size={18} />
            </Link>
            <span className="cta-footnote">Регистрация и работа с материалами в едином пространстве</span>
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="container footer-inner">
          <Link className="brand footer-brand" to="/">
            <span className="brand-icon">
              <ShieldCheck size={22} />
            </span>
            <span className="brand-name">
              Автор<span>Реестр</span>
            </span>
          </Link>
          <p>Система внутреннего реестра авторских материалов</p>
          <span className="footer-copy">© 2026 АвторРеестр</span>
        </div>
      </footer>
    </div>
  )
}

function ProtectedDashboard() {
  const { user, token } = useAuth()

  if (!token || !user) {
    return <Navigate to="/login" replace />
  }

  return <DashboardPage />
}

function ProtectedAdmin() {
  const { user, token } = useAuth()

  if (!token || !user) {
    return <Navigate to="/login" replace />
  }

  if (user.role !== 'admin') {
    return <Navigate to="/dashboard" replace />
  }

  return <AdminPage />
}

function App() {
  const { user, token } = useAuth()

  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route
        path="/login"
        element={token && user ? <Navigate to="/dashboard" replace /> : <LoginPage />}
      />
      <Route
        path="/register"
        element={token && user ? <Navigate to="/dashboard" replace /> : <RegisterPage />}
      />
      <Route path="/dashboard" element={<ProtectedDashboard />} />
      <Route path="/admin" element={<ProtectedAdmin />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
