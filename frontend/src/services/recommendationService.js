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

  // Mock recommendations (for development)
  mockRecommendations() {
    return {
      recommendations: [
        {
          product_id: 'PKT001',
          product_name: 'Paket For You',
          score: 0.92,
          reason: 'Based on your data usage patterns',
          price: 15000,
          quota_data_mb: 10240,
          quota_voice_min: 0,
          quota_sms: 0,
          validity_days: 7,
          cta_url: '/products/PKT001',
        },
        {
          product_id: 'PKT002',
          product_name: 'Paket For You',
          score: 0.88,
          reason: 'Popular in your segment',
          price: 25000,
          quota_data_mb: 20480,
          quota_voice_min: 0,
          quota_sms: 0,
          validity_days: 18,
          cta_url: '/products/PKT002',
        },
        {
          product_id: 'PKT003',
          product_name: 'Paket Mania',
          score: 0.85,
          reason: 'Based on your purchase frequency',
          price: 20000,
          quota_data_mb: 12288,
          quota_voice_min: 0,
          quota_sms: 0,
          validity_days: 28,
          cta_url: '/products/PKT003',
        },
      ],
      ab_variant: 'control',
      metadata: {
        latency_ms: 45,
        model_version: 'v1.0.0',
      },
    }
  },

  // Mock products
  mockProducts() {
    return {
      products: [
        {
          product_id: 'PKT001',
          product_name: 'Paket For You 10GB',
          product_family: 'For You',
          price: 15000,
          quota_data_mb: 10240,
          validity_days: 7,
          tags: ['data', 'basic'],
        },
        {
          product_id: 'PKT002',
          product_name: 'Paket For You 20GB',
          product_family: 'For You',
          price: 25000,
          quota_data_mb: 20480,
          validity_days: 18,
          tags: ['data', 'popular'],
        },
        {
          product_id: 'PKT003',
          product_name: 'Paket For You 25GB',
          product_family: 'For You',
          price: 30000,
          quota_data_mb: 25600,
          validity_days: 30,
          tags: ['data', 'premium'],
        },
        {
          product_id: 'PKT004',
          product_name: 'Paket Mania 12GB',
          product_family: 'Mania',
          price: 20000,
          quota_data_mb: 12288,
          validity_days: 28,
          tags: ['data', 'combo'],
        },
        {
          product_id: 'PKT005',
          product_name: 'Paket Mania 24GB',
          product_family: 'Mania',
          price: 35000,
          quota_data_mb: 24576,
          validity_days: 28,
          tags: ['data', 'combo'],
        },
        {
          product_id: 'PKT006',
          product_name: 'Paket Mania 30GB',
          product_family: 'Mania',
          price: 40000,
          quota_data_mb: 30720,
          validity_days: 28,
          tags: ['data', 'premium'],
        },
      ],
      total: 6,
    }
  },
}

export default recommendationService
