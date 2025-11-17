import React, { useEffect } from 'react'
import { CheckCircle, XCircle, AlertCircle, Info, X } from 'lucide-react'

/**
 * Toast notification component
 *
 * Types: success, error, warning, info
 */
const Toast = ({ type = 'info', message, onClose, duration = 5000 }) => {
  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        onClose?.()
      }, duration)

      return () => clearTimeout(timer)
    }
  }, [duration, onClose])

  const icons = {
    success: <CheckCircle className="w-6 h-6" />,
    error: <XCircle className="w-6 h-6" />,
    warning: <AlertCircle className="w-6 h-6" />,
    info: <Info className="w-6 h-6" />
  }

  const colors = {
    success: 'bg-green-50 border-green-500 text-green-800',
    error: 'bg-red-50 border-red-500 text-red-800',
    warning: 'bg-yellow-50 border-yellow-500 text-yellow-800',
    info: 'bg-blue-50 border-blue-500 text-blue-800'
  }

  const iconColors = {
    success: 'text-green-600',
    error: 'text-red-600',
    warning: 'text-yellow-600',
    info: 'text-blue-600'
  }

  return (
    <div
      className={`flex items-start gap-3 p-4 rounded-lg border-l-4 shadow-lg ${colors[type]} animate-slide-in-right`}
      style={{ minWidth: '320px', maxWidth: '480px' }}
    >
      <div className={iconColors[type]}>{icons[type]}</div>
      <p className="flex-1 text-sm font-medium">{message}</p>
      <button
        onClick={onClose}
        className="text-gray-400 hover:text-gray-600 transition-colors"
      >
        <X className="w-5 h-5" />
      </button>
    </div>
  )
}

export default Toast
