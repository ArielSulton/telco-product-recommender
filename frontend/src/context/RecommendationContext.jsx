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
    async (context = {}, limit = 5) => {
      // ✅ Single user check at the top (removed duplicate)
      if (!user?.id) {
        setRecommendations([])
        return
      }

      try {
        setLoading(true)
        setError(null)

        // Fetch from API
        const data = await recommendationService.getRecommendations(
          user.id,
          context,
          limit
        )

        setRecommendations(data.recommendations || [])
        setVariant(data.ab_variant)
        setMetadata(data.metadata)
      } catch (err) {
        setError(err.message || 'Failed to fetch recommendations')
        console.error('Recommendation fetch error:', err)
        setRecommendations([])
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
