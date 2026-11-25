
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, ShieldCheck } from 'lucide-react'
import { register } from '../services/api'
import { useAuth } from '../context/AuthContext'
import '../App.css'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { saveAuth } = useAuth()

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      const result = await register({ username, email, password })
      saveAuth(result)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка регистрации')
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
        <p className="eyebrow">СОЗДАНИЕ АККАУНТА</p>
        <h1>Регистрация</h1>
        <p className="auth-description">
          Создайте аккаунт, чтобы регистрировать и проверять авторские материалы.
        </p>

        <form onSubmit={handleSubmit} className="auth-form">
          <label htmlFor="username">Имя пользователя</label>
          <input
            id="username"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="Например, ivan_petrov"
            minLength={3}
            maxLength={50}
            pattern="[A-Za-z0-9_.-]+"
            title="Используйте латинские буквы, цифры, точку, дефис или подчёркивание"
            required
          />

          <label htmlFor="email">Электронная почта</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="name@example.com"
            required
          />

          <label htmlFor="password">Пароль</label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Не менее 10 символов"
            minLength={10}
            maxLength={128}
            required
          />

          {error && <div className="auth-error">{error}</div>}

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading ? 'Создаём аккаунт...' : 'Зарегистрироваться'}
          </button>
        </form>

        <p className="auth-switch">
          Уже есть аккаунт? <Link to="/login">Войти</Link>
        </p>
      </section>

      <p className="auth-footer">
        АвторРеестр · Защита интеллектуальной собственности
      </p>
    </main>
  )
}
