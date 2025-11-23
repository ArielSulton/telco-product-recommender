import { useState } from 'react'
import { CreditCard, Smartphone, Wallet, Check, X, ShoppingCart, AlertTriangle, Clock } from 'lucide-react'
import api from '../services/api'

const CheckoutModal = ({ isOpen, onClose, product, userBalance, onSuccess }) => {
  const [paymentMethod, setPaymentMethod] = useState('pulsa')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const paymentMethods = [
    {
      value: 'pulsa',
      label: 'Pulsa',
      icon: Smartphone,
      description: 'Bayar menggunakan saldo pulsa',
      available: userBalance >= (product?.price || 0)
    },
    {
      value: 'transfer',
      label: 'Transfer Bank',
      icon: CreditCard,
      description: 'Transfer via bank (coming soon)',
      available: false
    },
    {
      value: 'ewallet',
      label: 'E-Wallet',
      icon: Wallet,
      description: 'GoPay, OVO, Dana (coming soon)',
      available: false
    }
  ]

  const handleCheckout = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await api.post('/api/v1/purchases', {
        product_id: product.product_id,
        payment_method: paymentMethod
      })

      // Success!
      onSuccess?.(response.data)
      onClose()
    } catch (err) {
      console.error('Checkout failed:', err)
      setError(
        err.response?.data?.detail ||
        'Gagal melakukan pembelian. Silakan coba lagi.'
      )
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen || !product) return null

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999] p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-green-600 to-emerald-600 text-white p-6 rounded-t-2xl">
          <div className="flex justify-between items-start">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <ShoppingCart className="w-6 h-6" />
                <h2 className="text-2xl font-bold">Checkout</h2>
              </div>
              <p className="text-green-100">Konfirmasi pembelian Anda</p>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:bg-white/20 rounded-full p-2 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Product Summary */}
          <div className="bg-gradient-to-r from-gray-50 to-gray-100 rounded-xl p-5 border-2 border-gray-200">
            <h3 className="font-semibold text-gray-800 mb-3">Detail Paket</h3>

            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-600">Nama Paket</span>
                <span className="font-semibold text-gray-900">{product.product_name}</span>
              </div>

              {product.quota_data_mb && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Kuota Internet</span>
                  <span className="font-semibold text-indigo-600">
                    {(product.quota_data_mb / 1024).toFixed(1)} GB
                  </span>
                </div>
              )}

              {product.validity_days && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Masa Aktif</span>
                  <span className="font-semibold text-purple-600">
                    {product.validity_days} Hari
                  </span>
                </div>
              )}

              <div className="pt-3 mt-3 border-t-2 border-gray-300">
                <div className="flex justify-between items-center">
                  <span className="text-lg font-semibold text-gray-800">Total</span>
                  <span className="text-2xl font-bold text-green-600">
                    Rp {product.price?.toLocaleString('id-ID')}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Payment Method Selection */}
          <div>
            <h3 className="font-semibold text-gray-800 mb-3">Metode Pembayaran</h3>
            <div className="space-y-3">
              {paymentMethods.map((method) => {
                const Icon = method.icon
                const isSelected = paymentMethod === method.value
                const isDisabled = !method.available

                return (
                  <button
                    key={method.value}
                    onClick={() => method.available && setPaymentMethod(method.value)}
                    disabled={isDisabled}
                    className={`w-full p-4 rounded-xl border-2 transition-all text-left ${
                      isSelected && !isDisabled
                        ? 'border-green-600 bg-green-50 shadow-md'
                        : isDisabled
                        ? 'border-gray-200 bg-gray-50 opacity-50 cursor-not-allowed'
                        : 'border-gray-200 hover:border-green-300 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <Icon className={`w-6 h-6 mt-1 ${
                        isSelected ? 'text-green-600' : 'text-gray-600'
                      }`} />
                      <div className="flex-1">
                        <div className="font-semibold text-gray-800">
                          {method.label}
                          {!method.available && (
                            <span className="ml-2 text-xs text-gray-500">(Segera hadir)</span>
                          )}
                        </div>
                        <div className="text-sm text-gray-600 mt-1">{method.description}</div>
                        {method.value === 'pulsa' && (
                          <div className="text-sm mt-2">
                            <span className="text-gray-600">Saldo Anda: </span>
                            <span className={`font-semibold ${
                              userBalance >= product.price ? 'text-green-600' : 'text-red-600'
                            }`}>
                              Rp {userBalance?.toLocaleString('id-ID')}
                            </span>
                          </div>
                        )}
                      </div>
                      {isSelected && !isDisabled && (
                        <Check className="w-5 h-5 text-green-600" />
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border-2 border-red-200 rounded-lg p-4">
              <div className="flex gap-3">
                <X className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-red-800">{error}</div>
              </div>
            </div>
          )}

          {/* Balance Warning */}
          {paymentMethod === 'pulsa' && userBalance < product.price && (
            <div className="bg-yellow-50 border-2 border-yellow-200 rounded-lg p-4">
              <div className="flex gap-3">
                <AlertTriangle className="w-6 h-6 text-yellow-600 flex-shrink-0" />
                <div className="text-sm text-yellow-800">
                  <p className="font-semibold mb-1">Saldo tidak mencukupi</p>
                  <p>
                    Anda memerlukan tambahan Rp{' '}
                    {(product.price - userBalance).toLocaleString('id-ID')}{' '}
                    untuk melakukan pembelian ini.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 bg-gray-50 rounded-b-2xl flex justify-between gap-3">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-6 py-3 text-gray-700 hover:text-gray-900 font-semibold transition-colors rounded-lg hover:bg-white"
          >
            Batal
          </button>

          <button
            onClick={handleCheckout}
            disabled={
              loading ||
              (paymentMethod === 'pulsa' && userBalance < product.price)
            }
            className={`px-8 py-3 rounded-lg font-semibold transition-all ${
              loading || (paymentMethod === 'pulsa' && userBalance < product.price)
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-gradient-to-r from-green-600 to-emerald-600 text-white hover:shadow-lg'
            }`}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Clock className="w-5 h-5 animate-spin" />
                Memproses...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Check className="w-5 h-5" />
                Bayar Sekarang
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default CheckoutModal
