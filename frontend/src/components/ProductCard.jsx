import React, { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import useEventTracking from '../hooks/useEventTracking'

const ProductCard = ({ product, variant, showReason = false }) => {
  const navigate = useNavigate()
  const { trackView, trackClick } = useEventTracking()

  // Track view on mount
  useEffect(() => {
    if (product?.product_id) {
      trackView(product.product_id, variant)
    }
  }, [product?.product_id, variant, trackView])

  const handleViewDetail = () => {
    trackClick(product.product_id, variant, {
      source: 'product_card',
      action: 'view_detail',
    })
    navigate(`/products/${product.product_id}`)
  }

  const formatPrice = (price) => {
    return new Intl.NumberFormat('id-ID').format(price)
  }

  const formatData = (mb) => {
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(0)} GB`
    }
    return `${mb} MB`
  }

  return (
    <div className="card hover:scale-105 transition-transform duration-200">
      {/* Product Header */}
      <div className="mb-4">
        <h3 className="text-xl font-bold text-gray-900 mb-1">
          {product.product_name || product.product_family}
        </h3>
        {product.quota_data_mb && (
          <p className="text-3xl font-bold text-green-700">
            {formatData(product.quota_data_mb)}
          </p>
        )}
      </div>

      {/* Product Details */}
      <div className="space-y-2 mb-4">
        {product.validity_days && (
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Validity:</span>
            <span className="font-semibold text-gray-900">
              {product.validity_days} Days
            </span>
          </div>
        )}

        <div className="flex justify-between text-sm">
          <span className="text-gray-600">Price:</span>
          <span className="font-bold text-gray-900">
            Rp {formatPrice(product.price)}
          </span>
        </div>

        {product.score && (
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Match Score:</span>
            <span className="font-semibold text-green-700">
              {(product.score * 100).toFixed(0)}%
            </span>
          </div>
        )}
      </div>

      {/* Recommendation Reason */}
      {showReason && product.reason && (
        <div className="mb-4 p-3 bg-cyan-50 rounded-lg">
          <p className="text-xs text-gray-700 italic">
            💡 {product.reason}
          </p>
        </div>
      )}

      {/* CTA Button */}
      <button
        onClick={handleViewDetail}
        className="w-full btn-primary text-base"
        aria-label={`View details for ${product.product_name}`}
      >
        View Detail
      </button>

      {/* A/B Test Variant Indicator (development only) */}
      {variant && process.env.NODE_ENV === 'development' && (
        <div className="mt-2 text-xs text-gray-400 text-center">
          Variant: {variant}
        </div>
      )}
    </div>
  )
}

export default ProductCard
