import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import authService from '../services/authService'

const RegisterPage = () => {
  const navigate = useNavigate()

  const [formData, setFormData] = useState({
    phone: '',
    name: '',
    password: '',
    confirmPassword: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [validationErrors, setValidationErrors] = useState({})

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    })
    setError('')
    setValidationErrors({})
  }

  const validateForm = () => {
    const errors = {}

    // Validate phone
    if (!formData.phone) {
      errors.phone = 'Phone number is required'
    } else if (!/^08\d{8,13}$/.test(formData.phone)) {
      errors.phone = 'Invalid phone format. Must be 08xxxxxxxxxx (10-15 digits)'
    }

    // Validate name
    if (!formData.name || formData.name.trim().length < 2) {
      errors.name = 'Name must be at least 2 characters'
    }

    // Validate password
    if (!formData.password) {
      errors.password = 'Password is required'
    } else if (formData.password.length < 6) {
      errors.password = 'Password must be at least 6 characters'
    }

    // Validate confirm password
    if (formData.password !== formData.confirmPassword) {
      errors.confirmPassword = 'Passwords do not match'
    }

    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    // Validate form
    if (!validateForm()) {
      setLoading(false)
      return
    }

    try {
      // Call register API
      const response = await authService.register({
        phone: formData.phone,
        name: formData.name.trim(),
        password: formData.password,
      })

      // Auto-login after successful registration
      if (response.access_token) {
        // Navigate to dashboard
        navigate('/dashboard')
      }
    } catch (err) {
      console.error('Registration error:', err)
      setError(err.response?.data?.error?.message || err.message || 'Registration failed. Please try again.')
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
            CREATE YOUR <span className="text-green-700">ACCOUNT</span>
          </h1>
          <p className="text-gray-700">Join us and find the perfect package for you</p>
        </div>

        {/* Registration Form */}
        <div className="card">
          <h2 className="text-xl font-bold text-gray-900 mb-6 text-center">
            Register New Account
          </h2>

          {error && (
            <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Phone Number */}
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
                className={`input-field ${validationErrors.phone ? 'border-red-500' : ''}`}
                required
                autoComplete="tel"
              />
              {validationErrors.phone && (
                <p className="text-xs text-red-600 mt-1">{validationErrors.phone}</p>
              )}
            </div>

            {/* Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-semibold text-gray-700 mb-2">
                Full Name
              </label>
              <input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                placeholder="John Doe"
                className={`input-field ${validationErrors.name ? 'border-red-500' : ''}`}
                required
                autoComplete="name"
              />
              {validationErrors.name && (
                <p className="text-xs text-red-600 mt-1">{validationErrors.name}</p>
              )}
            </div>

            {/* Password */}
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
                placeholder="Min. 6 characters"
                className={`input-field ${validationErrors.password ? 'border-red-500' : ''}`}
                required
                autoComplete="new-password"
              />
              {validationErrors.password && (
                <p className="text-xs text-red-600 mt-1">{validationErrors.password}</p>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-semibold text-gray-700 mb-2">
                Confirm Password
              </label>
              <input
                type="password"
                id="confirmPassword"
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                placeholder="Re-enter password"
                className={`input-field ${validationErrors.confirmPassword ? 'border-red-500' : ''}`}
                required
                autoComplete="new-password"
              />
              {validationErrors.confirmPassword && (
                <p className="text-xs text-red-600 mt-1">{validationErrors.confirmPassword}</p>
              )}
            </div>

            <button
              type="submit"
              className="w-full btn-primary"
              disabled={loading}
            >
              {loading ? 'Creating Account...' : 'Create Account'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <span className="text-gray-700">Already have an account? </span>
            <Link
              to="/login"
              className="text-green-700 font-bold hover:text-green-800 underline"
            >
              Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default RegisterPage
