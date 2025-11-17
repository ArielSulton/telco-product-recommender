import React from 'react'

/**
 * Skeleton loading card component for better loading UX
 */
const SkeletonCard = () => {
  return (
    <div className="card animate-pulse">
      {/* Image skeleton */}
      <div className="w-full h-48 bg-gray-200 rounded-lg mb-4"></div>

      {/* Title skeleton */}
      <div className="h-6 bg-gray-200 rounded w-3/4 mb-3"></div>

      {/* Subtitle skeleton */}
      <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>

      {/* Price skeleton */}
      <div className="flex justify-between items-center mb-4">
        <div className="h-8 bg-gray-200 rounded w-1/3"></div>
        <div className="h-6 bg-gray-200 rounded w-1/4"></div>
      </div>

      {/* Button skeleton */}
      <div className="h-10 bg-gray-200 rounded w-full"></div>
    </div>
  )
}

export default SkeletonCard
