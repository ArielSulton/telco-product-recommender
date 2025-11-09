import React, { createContext, useState, useContext, useCallback } from 'react'
import recommendationService from '../services/recommendationService'
import { useAuth } from './AuthContext'

const RecommendationContext = createContext(null)

export const RecommendationProvider = ({ children }) => {
  const { user } = useAuth()
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [variant, setVariant] = useState(null)
  const [metadata, setMetadata] = useState(null)

  // Fetch recommendations
  const fetchRecommendations = useCallback(
    async (context = {}, limit = 5, useMock = false) => {
      if (!user?.id && !useMock) {
        setRecommendations([])
        return
      }

      try {
        setLoading(true)
        setError(null)

        let data
        if (useMock || !user?.id) {
          // Use mock data for development or non-authenticated users
          data = recommendationService.mockRecommendations()
        } else {
          // Fetch from API
          data = await recommendationService.getRecommendations(
            user.id,
            context,
            limit
          )
        }

        setRecommendations(data.recommendations || [])
        setVariant(data.ab_variant)
        setMetadata(data.metadata)
      } catch (err) {
        setError(err.message || 'Failed to fetch recommendations')
        console.error('Recommendation fetch error:', err)

        // Fallback to mock data on error
        const mockData = recommendationService.mockRecommendations()
        setRecommendations(mockData.recommendations || [])
      } finally {
        setLoading(false)
      }
    },
    [user]
  )

  // Clear recommendations
  const clearRecommendations = () => {
    setRecommendations([])
    setVariant(null)
    setMetadata(null)
    setError(null)
  }

  const value = {
    recommendations,
    loading,
    error,
    variant,
    metadata,
    fetchRecommendations,
    clearRecommendations,
  }

  return (
    <RecommendationContext.Provider value={value}>
      {children}
    </RecommendationContext.Provider>
  )
}

export const useRecommendations = () => {
  const context = useContext(RecommendationContext)
  if (!context) {
    throw new Error('useRecommendations must be used within RecommendationProvider')
  }
  return context
}

export default RecommendationContext
