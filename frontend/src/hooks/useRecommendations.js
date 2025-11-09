import { useContext } from 'react'
import RecommendationContext from '../context/RecommendationContext'

const useRecommendations = () => {
  const context = useContext(RecommendationContext)

  if (!context) {
    throw new Error('useRecommendations must be used within RecommendationProvider')
  }

  return context
}

export default useRecommendations
