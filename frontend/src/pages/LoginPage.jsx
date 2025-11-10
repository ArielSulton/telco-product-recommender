import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const LoginPage = () => {
  const navigate = useNavigate()
  const { login } = useAuth()

  const [formData, setFormData] = useState({
    phone: '',
    password: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    })
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      // Use mock login for development
      const authService = await import('../services/authService')
      authService.default.mockLogin(formData.phone, formData.password)

      // Redirect to dashboard
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-cyan-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center space-x-2 mb-6">
            <div className="w-16 h-16 bg-gradient-to-br from-green-600 to-cyan-400 rounded-full flex items-center justify-center">
              <span className="text-white font-bold text-3xl">P</span>
            </div>
            <span className="text-2xl font-bold text-gray-900">PAKETIFY</span>
          </Link>

          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            WELCOME TO <span className="text-green-700">PAKETIFY</span>
          </h1>
          <p className="text-gray-700">
            Choose the Internet Package That Suits You
          </p>
        </div>

        {/* Login Form */}
        <div className="card">
          <h2 className="text-xl font-bold text-gray-900 mb-6 text-center">
            Login to your account
          </h2>

          {error && (
            <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded-lg">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="phone" className="block text-sm font-semibold text-gray-700 mb-2">
                No. Telp
              </label>
              <input
                type="tel"
                id="phone"
                name="phone"
                value={formData.phone}
                onChange={handleChange}
                placeholder="08123456789"
                className="input-field"
                required
                autoComplete="tel"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-semibold text-gray-700 mb-2">
                Password
              </label>
              <input
                type="password"
                id="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="Enter your password"
                className="input-field"
                required
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              className="w-full btn-primary"
              disabled={loading}
            >
              {loading ? 'Signing In...' : 'Sign In'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <Link
              to="/forgot-password"
              className="text-sm text-gray-700 hover:text-green-700 underline"
            >
              Forgot password?
            </Link>
          </div>

          <div className="mt-6 text-center">
            <span className="text-gray-700">Not a member? </span>
            <Link
              to="/register"
              className="text-green-700 font-bold hover:text-green-800 underline"
            >
              Register Now
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
