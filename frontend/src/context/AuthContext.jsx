import React, { createContext, useState, useEffect, useContext } from 'react'
import authService from '../services/authService'

const AuthContext = createContext(null)

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Initialize auth state from localStorage
  useEffect(() => {
    const initAuth = () => {
      const currentUser = authService.getCurrentUser()
      setUser(currentUser)
      setLoading(false)
    }

    initAuth()
  }, [])

  // Login
  const login = async (phone, password) => {
    try {
      setError(null)
      const data = await authService.login(phone, password)
      setUser(data.user)
      return data
    } catch (err) {
      setError(err.message || 'Login failed')
      throw err
    }
  }

  // Register
  const register = async (userData) => {
    try {
      setError(null)
      const data = await authService.register(userData)
      return data
    } catch (err) {
      setError(err.message || 'Registration failed')
      throw err
    }
  }

  // Logout
  const logout = () => {
    authService.logout()
    setUser(null)
  }

  // Update profile
  const updateProfile = async (userData) => {
    try {
      setError(null)
      const updatedUser = await authService.updateProfile(userData)
      setUser(updatedUser)
      return updatedUser
    } catch (err) {
      setError(err.message || 'Profile update failed')
      throw err
    }
  }

  // Refresh user data
  const refreshUser = async () => {
    try {
      const userData = await authService.getUserProfile()
      setUser(userData)
      return userData
    } catch (err) {
      console.error('Failed to refresh user:', err)
      return null
    }
  }

  const value = {
    user,
    loading,
    error,
    isAuthenticated: !!user,
    login,
    register,
    logout,
    updateProfile,
    refreshUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}

export default AuthContext
