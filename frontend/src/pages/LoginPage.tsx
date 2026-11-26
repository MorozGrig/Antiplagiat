
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, ShieldCheck } from 'lucide-react'
import { login } from '../services/api'
import { useAuth } from '../context/AuthContext'
import '../App.css'

export default function LoginPage() {
  const navigate = useNavigate()
  const { saveAuth } = useAuth()

  const [usernameOrEmail, setUsernameOrEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (loading) return

    setError('')
    setLoading(true)

    try {
      const result = await login({
        username_or_email: usernameOrEmail.trim(),
        password,
      })

      saveAuth(result)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка входа')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-top">
        <Link to="/" className="auth-back">
          <ArrowLeft size={18} />
          На главную
        </Link>
        <Link to="/" className="brand">
          <span className="brand-mark"><ShieldCheck size={21} /></span>
          АвторРеестр
        </Link>
      </div>

      <section className="auth-card">
        <div className="auth-icon"><ShieldCheck size={26} /></div>
        <p className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</p>
        <h1>С возвращением</h1>
        <p className="auth-description">
          Войдите, чтобы управлять своими авторскими материалами.
        </p>

        <form onSubmit={handleSubmit} className="auth-form">
          <label htmlFor="username">Имя пользователя или email</label>
          <input
  id="username"
  type="text"
  autoComplete="username"
  autoCapitalize="none"
  spellCheck={false}
  value={usernameOrEmail}
  onChange={(event) => setUsernameOrEmail(event.target.value)}
  placeholder="Введите имя пользователя или email"
  required
  minLength={3}
  maxLength={100}
/>

          <label htmlFor="password">Пароль</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Введите пароль"
            required
            maxLength={128}
          />

          {error && <div className="auth-error">{error}</div>}

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading ? 'Выполняется вход...' : 'Войти в аккаунт'}
          </button>
        </form>

        <p className="auth-switch">
          Ещё нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
        </p>
      </section>

      <p className="auth-footer">
        АвторРеестр · Защита интеллектуальной собственности
      </p>
    </main>
  )
}
