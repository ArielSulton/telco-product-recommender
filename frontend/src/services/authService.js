import api from './api'

const authService = {
  // Login
  async login(phone, password) {
    try {
      const response = await api.post('/api/v1/auth/login', {
        phone,
        password,
      })

      if (response.data.access_token) {
        localStorage.setItem('token', response.data.access_token)
        localStorage.setItem('user', JSON.stringify(response.data.user))
      }

      return response.data
    } catch (error) {
      throw error
    }
  },

  // Register
  async register(userData) {
    try {
      const response = await api.post('/api/v1/auth/register', userData)
      return response.data
    } catch (error) {
      throw error
    }
  },

  // Logout
  logout() {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
  },

  // Get current user
  getCurrentUser() {
    const userStr = localStorage.getItem('user')
    if (userStr) {
      try {
        return JSON.parse(userStr)
      } catch (e) {
        return null
      }
    }
    return null
  },

  // Check if authenticated
  isAuthenticated() {
    return !!localStorage.getItem('token')
  },

  // Get user profile
  async getUserProfile() {
    try {
      const response = await api.get('/api/v1/users/me')
      localStorage.setItem('user', JSON.stringify(response.data))
      return response.data
    } catch (error) {
      throw error
    }
  },

  // Update user profile
  async updateProfile(userData) {
    try {
      const response = await api.put('/api/v1/users/me', userData)
      localStorage.setItem('user', JSON.stringify(response.data))
      return response.data
    } catch (error) {
      throw error
    }
  },

  // Mock login (for development without backend)
  mockLogin(phone) {
    const mockUser = {
      id: '123e4567-e89b-12d3-a456-426614174000',
      phone: phone,
      name: 'Demo User',
      segment: 2,
      balance: 100000,
    }
    const mockToken = 'mock-jwt-token-' + Date.now()

    localStorage.setItem('token', mockToken)
    localStorage.setItem('user', JSON.stringify(mockUser))

    return {
      access_token: mockToken,
      user: mockUser,
    }
  },
}

export default authService
