import api from './api'

const eventService = {
  // Track event
  async trackEvent(eventData) {
    try {
      const response = await api.post('/events', {
        user_id: eventData.userId,
        product_id: eventData.productId,
        event_type: eventData.eventType, // 'view', 'click', 'subscribe'
        timestamp: new Date().toISOString(),
        session_id: this.getSessionId(),
        ab_variant: eventData.variant,
        metadata: eventData.metadata || {},
      })
      return response.data
    } catch (error) {
      // Fail silently for event tracking to not disrupt user experience
      console.error('Failed to track event:', error)
      return null
    }
  },

  // Get or create session ID
  getSessionId() {
    let sessionId = sessionStorage.getItem('session_id')
    if (!sessionId) {
      sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      sessionStorage.setItem('session_id', sessionId)
    }
    return sessionId
  },

  // Batch event tracking (for performance)
  eventQueue: [],
  batchTimeout: null,

  queueEvent(eventData) {
    this.eventQueue.push(eventData)

    // Clear existing timeout
    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout)
    }

    // Send batch after 500ms of no new events
    this.batchTimeout = setTimeout(() => {
      this.flushEventQueue()
    }, 500)
  },

  async flushEventQueue() {
    if (this.eventQueue.length === 0) return

    const events = [...this.eventQueue]
    this.eventQueue = []

    try {
      await Promise.all(events.map((event) => this.trackEvent(event)))
    } catch (error) {
      console.error('Failed to flush event queue:', error)
    }
  },
}

export default eventService
