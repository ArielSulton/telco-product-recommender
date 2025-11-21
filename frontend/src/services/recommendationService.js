import api from './api'

const recommendationService = {
  // Get personalized recommendations
  async getRecommendations(userId, context = {}, limit = 5) {
    try {
      const response = await api.post('/api/v1/recommend', {
        user_id: userId,
        context: context,
        limit: limit,
      })
      return response.data
    } catch (error) {
      console.error('Failed to fetch recommendations:', error)
      throw error
    }
  },

  // Get product details
  async getProduct(productId) {
    try {
      const response = await api.get(`/api/v1/products/${productId}`)
      return response.data
    } catch (error) {
      console.error('Failed to fetch product:', error)
      throw error
    }
  },

  // Get all products
  async getProducts(filters = {}) {
    try {
      const params = new URLSearchParams()

      if (filters.family) params.append('family', filters.family)
      if (filters.limit) params.append('limit', filters.limit)
      if (filters.offset) params.append('offset', filters.offset)

      const response = await api.get(`/api/v1/products?${params.toString()}`)
      return response.data
    } catch (error) {
      console.error('Failed to fetch products:', error)
      throw error
    }
  },
}

export default recommendationService
