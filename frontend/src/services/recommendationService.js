import api from './api'

const recommendationService = {
  // Get personalized recommendations (v2 - RF model with A/B testing)
  async getRecommendationsV2(userId, options = {}) {
    try {
      const response = await api.post(
        '/api/v1/recommend/v2',
        {
          user_id: userId,
          k: options.limit || 5,
          include_explanations: options.includeExplanations ?? true,
          min_confidence: options.minConfidence || 0.05,
        },
        {
          headers: options.forceVariant
            ? {
                'X-AB-Variant': options.forceVariant,
              }
            : {},
        }
      )
      return response.data
    } catch (error) {
      console.error('Failed to fetch recommendations v2:', error)
      throw error
    }
  },

  // Get personalized recommendations (legacy v1)
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
