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

      // Store token and user data after successful registration
      if (response.data.access_token) {
        localStorage.setItem('token', response.data.access_token)
        localStorage.setItem('user', JSON.stringify(response.data.user))
      }

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
      const response = await api.get('/api/v1/auth/me')
      if (response.data.user) {
        localStorage.setItem('user', JSON.stringify(response.data.user))
        return response.data.user
      }
      return response.data
    } catch (error) {
      throw error
    }
  },

  // Update user profile
  async updateProfile(userData) {
    try {
      const response = await api.put('/api/v1/users/me', userData)
      // Backend returns {user: {...}, message: "..."}
      if (response.data.user) {
        localStorage.setItem('user', JSON.stringify(response.data.user))
        return response.data.user
      }
      return response.data
    } catch (error) {
      throw error
    }
  },

  // Mock login (for development without backend)
  mockLogin(phone, password) {
    // ✅ SECURITY: Only available in development mode
    if (import.meta.env.MODE !== 'development') {
      throw new Error('Mock login is not available in production. Please use real authentication.')
    }

    // Development-only credentials (NOT exposed in production builds)
    const validCredentials = [
      { phone: '08123456789', password: 'user123', name: 'Demo User', segment: 2, role: 'user' },
      { phone: 'admin', password: 'admin123', name: 'Admin User', segment: 1, role: 'admin' },
      { phone: '08111111111', password: 'demo', name: 'Test User', segment: 3, role: 'user' },
    ]

    // Check credentials
    const credential = validCredentials.find(
      c => c.phone === phone && c.password === password
    )

    if (!credential) {
      throw new Error('Invalid phone number or password')
    }

    const mockUser = {
      id: '123e4567-e89b-12d3-a456-426614174000',
      phone: credential.phone,
      name: credential.name,
      segment: credential.segment,
      role: credential.role,
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
