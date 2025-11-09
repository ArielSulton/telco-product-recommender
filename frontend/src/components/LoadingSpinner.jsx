import React from 'react'

const LoadingSpinner = ({ size = 'md', text = '' }) => {
  const sizeClasses = {
    sm: 'w-8 h-8 border-2',
    md: 'w-16 h-16 border-4',
    lg: 'w-24 h-24 border-4',
    xl: 'w-32 h-32 border-4',
  }

  return (
    <div className="flex flex-col items-center justify-center">
      <div
        className={`loading-spinner ${sizeClasses[size]}`}
        role="status"
        aria-label="Loading"
      />
      {text && <p className="mt-4 text-gray-600 font-medium">{text}</p>}
    </div>
  )
}

export default LoadingSpinner
