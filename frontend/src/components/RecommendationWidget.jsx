import React, { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import ProductCard from './ProductCard'
import SkeletonCard from './SkeletonCard'
import EmptyState from './EmptyState'
import useRecommendations from '../hooks/useRecommendations'

const RecommendationWidget = ({ title = 'Recommended for You', limit = 3 }) => {
  const navigate = useNavigate()
  const { recommendations, loading, error, variant, fetchRecommendations } =
    useRecommendations()

  useEffect(() => {
    fetchRecommendations({}, limit)
  }, [fetchRecommendations, limit])

  if (loading) {
    return (
      <section className="py-8">
        <h2 className="section-title">{title}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: limit }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
      </section>
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
    return (
      <section className="py-8">
        <h2 className="section-title">{title}</h2>
        <div className="card">
          <EmptyState
            type="recommendations"
            action={() => navigate('/products')}
            actionLabel="Jelajahi Semua Paket"
          />
        </div>
      </section>
    )
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
            onClick={() => fetchRecommendations({}, limit + 3)}
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
