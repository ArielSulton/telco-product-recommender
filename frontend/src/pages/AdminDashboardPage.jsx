import React, { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { Navigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import Footer from '../components/Footer'
import EmptyState from '../components/EmptyState'
import { Users, TrendingUp, Package, Edit, Trash2, Plus, Save, RefreshCw, DollarSign, AlertTriangle, BookOpen } from 'lucide-react'
import api from '../services/api'

const AdminDashboardPage = () => {
  const { user } = useAuth()
  const toast = useToast()

  // State for stats
  const [stats, setStats] = useState({
    total_users: 0,
    total_purchases: 0,
    total_revenue: 0,
    avg_data_usage_gb: 0,
    active_products: 0
  })

  // Mock recommendations data (unchanged for now)
  const [recommendations] = useState([
    { id: 'C001', username: 'John Doe', device: 'Realme', usage: '12.3 GB', offer: 'Data Booster' },
    { id: 'C002', username: 'John', device: 'Vivo', usage: '8 GB', offer: 'General Offer' },
    { id: 'C003', username: 'Doe', device: 'Samsung', usage: '9.7 GB', offer: 'Top-up Promo' },
    { id: 'C004', username: 'John', device: 'Oppo', usage: '10 GB', offer: 'Data Booster' },
    { id: 'C005', username: 'Doe', device: 'Apple', usage: '8.5 GB', offer: 'General Offer' },
    { id: 'C006', username: 'John', device: 'Apple', usage: '20.4 GB', offer: 'Top-up Promo' },
    { id: 'C007', username: 'Doe', device: 'Apple', usage: '5 GB', offer: 'Top-up Promo' },
    { id: 'C008', username: 'John', device: 'Apple', usage: '19.2 GB', offer: 'Data Booster' },
  ])

  // Products data from API
  const [packages, setPackages] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)

  const [editingId, setEditingId] = useState(null)
  const [formData, setFormData] = useState({
    name: '',
    price: '',
    quota: '',
    benefit: '',
  })

  // Fetch products and stats from API
  const fetchProductsAndStats = useCallback(async () => {
    setLoading(true)
    try {
      // Fetch products
      const productsResponse = await api.get('/api/v1/admin/products')
      const products = productsResponse.data || []

      // Map to frontend format
      const mappedProducts = products.map(p => ({
        id: p.product_id,
        name: p.product_name,
        benefit: p.benefit,
        price: p.price,
        quota: Math.round(p.quota_data_mb / 1024), // Convert MB to GB
        product_id: p.product_id,
        quota_mb: p.quota_data_mb
      }))

      setPackages(mappedProducts)

      // Fetch stats
      const statsResponse = await api.get('/api/v1/admin/stats')
      setStats(statsResponse.data)

    } catch (error) {
      console.error('Failed to fetch admin data:', error)
      toast.error('Gagal memuat data admin')
    } finally {
      setLoading(false)
    }
  }, [toast])

  // Fetch products and stats on mount
  useEffect(() => {
    fetchProductsAndStats()
  }, [fetchProductsAndStats])

  // Redirect if not admin (after all hooks)
  if (!user || user.role !== 'admin') {
    return <Navigate to="/dashboard" replace />
  }

  // Sync products (refresh from database)
  const handleSyncProducts = async () => {
    setSyncing(true)
    try {
      await fetchProductsAndStats()
      toast.success('Produk berhasil di-sync dari database!')
    } catch (error) {
      console.error('Sync failed:', error)
      toast.error('Gagal sync produk')
    } finally {
      setSyncing(false)
    }
  }

  // Handle form input
  const handleInputChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
  }

  // Add new package
  const handleAddPackage = async () => {
    // Validate form
    if (!formData.name || !formData.price || !formData.quota) {
      toast.error('Mohon isi semua field yang diperlukan')
      return
    }

    try {
      const response = await api.post('/api/v1/admin/products', {
        product_name: formData.name,
        product_family: 'Custom Package',
        quota_data_mb: parseInt(formData.quota),
        validity_days: 30,
        price: parseInt(formData.price)
      })

      // Add to local state
      const newPackage = {
        id: response.data.product_id,
        name: response.data.product_name,
        price: response.data.price,
        quota: response.data.quota_data_mb,
        benefit: response.data.benefit
      }
      setPackages([...packages, newPackage])

      // Reset form
      setFormData({ name: '', price: '', quota: '', benefit: '' })
      toast.success('Produk berhasil ditambahkan!')
    } catch (error) {
      console.error('Failed to add product:', error)
      toast.error('Gagal menambahkan produk: ' + (error.response?.data?.detail || 'Unknown error'))
    }
  }

  // Edit package
  const handleEdit = (pkg) => {
    setEditingId(pkg.id)
    setFormData({
      name: pkg.name,
      price: pkg.price.toString(),
      quota: pkg.quota.toString(),
      benefit: pkg.benefit,
    })
  }

  // Update package
  const handleUpdate = async () => {
    if (!editingId) return

    // Validate form
    if (!formData.name || !formData.price || !formData.quota) {
      toast.error('Mohon isi semua field yang diperlukan')
      return
    }

    try {
      const response = await api.put(`/api/v1/admin/products/${editingId}`, {
        product_name: formData.name,
        quota_data_mb: parseInt(formData.quota),
        price: parseInt(formData.price)
      })

      // Update local state
      setPackages(packages.map(pkg =>
        pkg.id === editingId
          ? {
              id: response.data.product_id,
              name: response.data.product_name,
              price: response.data.price,
              quota: response.data.quota_data_mb,
              benefit: response.data.benefit
            }
          : pkg
      ))

      // Reset form
      setEditingId(null)
      setFormData({ name: '', price: '', quota: '', benefit: '' })
      toast.success('Produk berhasil diupdate!')
    } catch (error) {
      console.error('Failed to update product:', error)
      toast.error('Gagal mengupdate produk: ' + (error.response?.data?.detail || 'Unknown error'))
    }
  }

  // Delete package
  const handleDelete = async (id) => {
    if (window.confirm('Apakah Anda yakin ingin menghapus produk ini?')) {
      try {
        await api.delete(`/api/v1/admin/products/${id}`)

        // Remove from local state
        setPackages(packages.filter(pkg => pkg.id !== id))
        toast.success('Produk berhasil dihapus!')
      } catch (error) {
        console.error('Failed to delete product:', error)
        const errorMsg = error.response?.data?.detail || 'Unknown error'

        if (errorMsg.includes('purchase')) {
          toast.error('Tidak bisa menghapus produk yang sudah dibeli user')
        } else {
          toast.error('Gagal menghapus produk: ' + errorMsg)
        }
      }
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-cyan-50">
      <Navbar />

      <main className="flex-1 container mx-auto px-4 py-8 animate-fade-in">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Admin Dashboard</h1>
        </div>

        {/* Stats Cards */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="card animate-pulse">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-gray-200 rounded-full"></div>
                  <div className="flex-1 space-y-2">
                    <div className="h-3 bg-gray-200 rounded w-24"></div>
                    <div className="h-6 bg-gray-200 rounded w-16"></div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              <div className="card hover-lift glass-card border-2 border-green-200">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-green-100 rounded-full">
                    <Users className="w-6 h-6 text-green-700" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700">TOTAL USERS</h3>
                    <p className="text-2xl font-bold text-gray-900">{stats.total_users.toLocaleString()}</p>
                  </div>
                </div>
              </div>

              <div className="card hover-lift glass-card border-2 border-cyan-200">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-cyan-100 rounded-full">
                    <TrendingUp className="w-6 h-6 text-cyan-700" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700">AVG DATA USAGE</h3>
                    <p className="text-2xl font-bold text-gray-900">{stats.avg_data_usage_gb.toFixed(1)} GB</p>
                  </div>
                </div>
              </div>

              <div className="card hover-lift glass-card border-2 border-purple-200">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-purple-100 rounded-full">
                    <Package className="w-6 h-6 text-purple-700" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700">TOTAL PURCHASES</h3>
                    <p className="text-2xl font-bold text-gray-900">{stats.total_purchases.toLocaleString()}</p>
                  </div>
                </div>
              </div>

              <div className="card hover-lift glass-card border-2 border-yellow-200">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-yellow-100 rounded-full">
                    <DollarSign className="w-6 h-6 text-yellow-700" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700">TOTAL REVENUE</h3>
                    <p className="text-2xl font-bold text-gray-900">Rp {(stats.total_revenue / 1000).toFixed(0)}K</p>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {/* Offer Recommendation Table */}
        <section className="mb-8">
          <div className="card">
            <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">Offer Recommendation</h2>

            {recommendations.length === 0 ? (
              <EmptyState
                type="analytics"
                title="Belum Ada Rekomendasi"
                description="Sistem rekomendasi akan menampilkan penawaran personal untuk pengguna berdasarkan aktivitas dan preferensi mereka."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b-2 border-gray-200">
                      <th className="px-4 py-3 text-left font-bold text-gray-900">ID</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Username</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Device</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Usage</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Offer</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recommendations.map((rec, index) => (
                      <tr key={rec.id} className={index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                        <td className="px-4 py-3 text-gray-900">{rec.id}</td>
                        <td className="px-4 py-3 text-gray-900">{rec.username}</td>
                        <td className="px-4 py-3 text-gray-900">{rec.device}</td>
                        <td className="px-4 py-3 text-gray-900">{rec.usage}</td>
                        <td className="px-4 py-3 text-gray-900">{rec.offer}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>

        {/* Manage Data Packages */}
        <section>
          <div className="card">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Manage Data Packages</h2>
              <button
                onClick={handleSyncProducts}
                disabled={syncing}
                className="inline-flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RefreshCw className={`w-5 h-5 ${syncing ? 'animate-spin' : ''}`} />
                {syncing ? 'Syncing...' : 'Sync Products'}
              </button>
            </div>

            {/* Packages Table */}
            {packages.length === 0 ? (
              <div className="mb-8">
                <EmptyState
                  type="products"
                  action={handleSyncProducts}
                  actionLabel="Sync Products dari Database"
                />
              </div>
            ) : (
              <div className="overflow-x-auto mb-8">
                <table className="w-full">
                  <thead>
                    <tr className="border-b-2 border-gray-200">
                      <th className="px-4 py-3 text-left font-bold text-gray-900">No</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Data Packages Name</th>
                      <th className="px-4 py-3 text-left font-bold text-gray-900">Benefit</th>
                      <th className="px-4 py-3 text-center font-bold text-gray-900">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {packages.map((pkg, index) => (
                      <tr key={pkg.id} className={index % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                        <td className="px-4 py-3 text-gray-900">{index + 1}.</td>
                        <td className="px-4 py-3 text-gray-900">{pkg.name}</td>
                        <td className="px-4 py-3 text-gray-900">{pkg.benefit}</td>
                        <td className="px-4 py-3 text-center">
                          <button
                            onClick={() => handleEdit(pkg)}
                            className="inline-flex items-center gap-1 px-3 py-1 bg-cyan-500 hover:bg-cyan-600 text-white rounded mr-2 transition-colors"
                          >
                            <Edit className="w-4 h-4" />
                            EDIT
                          </button>
                          <button
                            onClick={() => handleDelete(pkg.id)}
                            className="inline-flex items-center gap-1 px-3 py-1 bg-red-500 hover:bg-red-600 text-white rounded transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                            HAPUS
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Add/Edit Package Form */}
            <div className="border-t-2 border-gray-200 pt-6">
              <h3 className="text-xl font-bold text-gray-900 mb-4">
                {editingId ? 'Edit Package' : 'Add New Package'}
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-gray-700 font-semibold mb-2">Nama Paket</label>
                  <input
                    type="text"
                    name="name"
                    value={formData.name}
                    onChange={handleInputChange}
                    className="input-field"
                    placeholder="e.g., Paket Hemat"
                  />
                </div>

                <div>
                  <label className="block text-gray-700 font-semibold mb-2">Harga (Rp)</label>
                  <input
                    type="number"
                    name="price"
                    value={formData.price}
                    onChange={handleInputChange}
                    className="input-field"
                    placeholder="e.g., 50000"
                  />
                </div>

                <div>
                  <label className="block text-gray-700 font-semibold mb-2">Kuota Data (GB)</label>
                  <input
                    type="number"
                    name="quota"
                    value={formData.quota}
                    onChange={handleInputChange}
                    className="input-field"
                    placeholder="e.g., 15"
                  />
                </div>

                <div>
                  <label className="block text-gray-700 font-semibold mb-2">Benefit Tambahan</label>
                  <input
                    type="text"
                    name="benefit"
                    value={formData.benefit}
                    onChange={handleInputChange}
                    className="input-field"
                    placeholder="e.g., + Chat, + Youtube"
                  />
                </div>
              </div>

              <div className="flex gap-3">
                {editingId ? (
                  <>
                    <button
                      onClick={handleUpdate}
                      className="btn-primary inline-flex items-center gap-2 active-press"
                    >
                      <Save className="w-5 h-5" />
                      Update
                    </button>
                    <button
                      onClick={() => {
                        setEditingId(null)
                        setFormData({ name: '', price: '', quota: '', benefit: '' })
                      }}
                      className="btn-secondary active-press"
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <button
                    onClick={handleAddPackage}
                    className="btn-primary inline-flex items-center gap-2 active-press"
                  >
                    <Plus className="w-5 h-5" />
                    Simpan
                  </button>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* ML Model Management */}
        <section className="mt-8">
          <div className="card">
            <h2 className="text-2xl font-bold text-gray-900 mb-6 text-center">ML Model Management</h2>

            <div className="bg-yellow-50 border-2 border-yellow-300 rounded-lg p-6 mb-6">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-8 h-8 text-yellow-600 flex-shrink-0 mt-1" />
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-yellow-900 mb-2">Fitur dalam Pengembangan</h3>
                  <p className="text-yellow-800">
                    Integrasi dengan Airflow dan MLflow masih dalam tahap pengembangan.
                    Untuk saat ini, gunakan Airflow UI dan MLflow UI langsung untuk monitoring model.
                  </p>
                  <div className="mt-4 space-y-2 text-sm">
                    <p className="text-yellow-700">
                      <span className="font-semibold">Airflow UI:</span> http://localhost:8080 (username: airflow, password: airflow)
                    </p>
                    <p className="text-yellow-700">
                      <span className="font-semibold">MLflow UI:</span> http://localhost:5000
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="border-2 border-gray-200 rounded-lg p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-4">Model Status</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-700">Current Model:</span>
                    <span className="font-semibold text-gray-900">K-Means Segmentation</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Last Training:</span>
                    <span className="font-semibold text-gray-900">Weekly (Sunday 2 AM)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-700">Status:</span>
                    <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-semibold">
                      Production
                    </span>
                  </div>
                </div>
              </div>

              <div className="border-2 border-gray-200 rounded-lg p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-4">Manual Retraining</h3>
                <p className="text-gray-700 mb-4 text-sm">
                  Trigger manual model retraining outside of scheduled runs.
                  Requires Airflow service to be running.
                </p>
                <button
                  disabled
                  className="w-full btn-primary inline-flex items-center justify-center gap-2 opacity-50 cursor-not-allowed"
                >
                  <RefreshCw className="w-5 h-5" />
                  Trigger Retraining (Coming Soon)
                </button>
              </div>
            </div>

            <div className="mt-6 border-2 border-blue-200 bg-blue-50 rounded-lg p-6">
              <h3 className="text-lg font-bold text-blue-900 mb-3 flex items-center gap-2">
                <BookOpen className="w-5 h-5" />
                Model Information
              </h3>
              <div className="space-y-2 text-sm text-blue-800">
                <p><span className="font-semibold">Segmentation:</span> K-Means clustering with 5 segments</p>
                <p><span className="font-semibold">Collaborative Filtering:</span> LightFM with WARP loss</p>
                <p><span className="font-semibold">Ranking:</span> XGBoost pairwise ranking model</p>
                <p><span className="font-semibold">Drift Detection:</span> PSI threshold ≥ 0.2 triggers retraining</p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  )
}

export default AdminDashboardPage
