import React, { useEffect } from 'react'
import ProductCard from './ProductCard'
import LoadingSpinner from './LoadingSpinner'
import useRecommendations from '../hooks/useRecommendations'

const RecommendationWidget = ({ title = 'Recommended for You', limit = 3, useMock = false }) => {
  const { recommendations, loading, error, variant, fetchRecommendations } =
    useRecommendations()

  useEffect(() => {
    fetchRecommendations({}, limit, useMock)
  }, [limit, useMock])

  if (loading) {
    return (
      <div className="py-12">
        <h2 className="section-title text-center">{title}</h2>
        <div className="flex justify-center">
          <LoadingSpinner text="Loading recommendations..." />
        </div>
      </div>
    )
  }

  if (error && !recommendations.length) {
    return (
      <div className="py-12">
        <h2 className="section-title text-center">{title}</h2>
        <div className="card max-w-md mx-auto text-center">
          <p className="text-gray-600">
            Unable to load recommendations. Please try again later.
          </p>
        </div>
      </div>
    )
  }

  if (!recommendations.length) {
    return null
  }

  return (
    <section className="py-8">
      <h2 className="section-title">{title}</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {recommendations.slice(0, limit).map((product) => (
          <ProductCard
            key={product.product_id}
            product={product}
            variant={variant}
            showReason={true}
          />
        ))}
      </div>

      {recommendations.length > limit && (
        <div className="text-center mt-8">
          <button
            onClick={() => fetchRecommendations({}, limit + 3, useMock)}
            className="btn-secondary"
          >
            Load More Recommendations
          </button>
        </div>
      )}
    </section>
  )
}

export default RecommendationWidget
