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

  // Fetch recommendations (v2 with fallback to v1)
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

        let data

        // Try v2 API first (RF model with A/B testing)
        try {
          data = await recommendationService.getRecommendationsV2(user.id, {
            limit,
            includeExplanations: true,
            minConfidence: 0.05,
          })

          // V2 response structure
          setRecommendations(data.recommendations || [])
          setVariant(data.ab_variant || null)
          setMetadata({
            model_version: data.model_version,
            inference_time_ms: data.inference_time_ms,
            timestamp: data.timestamp,
          })

          console.log(
            `✅ Recommendations from ${data.model_version} (${data.ab_variant})`
          )
        } catch (v2Error) {
          // Fallback to v1 API if v2 fails
          console.warn(
            'RF v2 API failed, falling back to legacy v1:',
            v2Error.message
          )

          data = await recommendationService.getRecommendations(
            user.id,
            context,
            limit
          )

          // V1 response structure (direct array)
          setRecommendations(data.recommendations || data || [])
          setVariant('legacy_fallback')
          setMetadata({
            model_version: 'hybrid_v1',
            fallback_reason: v2Error.message,
          })

          console.log('✅ Recommendations from legacy v1 (fallback)')
        }
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
