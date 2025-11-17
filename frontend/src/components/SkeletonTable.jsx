import React from 'react'

/**
 * Skeleton loading table rows
 */
const SkeletonTableRow = () => {
  return (
    <tr className="animate-pulse">
      <td className="px-4 py-3">
        <div className="h-4 bg-gray-200 rounded w-8"></div>
      </td>
      <td className="px-4 py-3">
        <div className="h-4 bg-gray-200 rounded w-32"></div>
      </td>
      <td className="px-4 py-3">
        <div className="h-4 bg-gray-200 rounded w-24"></div>
      </td>
      <td className="px-4 py-3 text-center">
        <div className="h-8 bg-gray-200 rounded w-24 mx-auto"></div>
      </td>
    </tr>
  )
}

const SkeletonTable = ({ rows = 5 }) => {
  return (
    <>
      {Array.from({ length: rows }).map((_, index) => (
        <SkeletonTableRow key={index} />
      ))}
    </>
  )
}

export default SkeletonTable
export { SkeletonTableRow }
