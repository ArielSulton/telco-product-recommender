import { useCallback } from 'react'
import eventService from '../services/eventService'
import { useAuth } from '../context/AuthContext'

const useEventTracking = () => {
  const { user } = useAuth()

  const trackEvent = useCallback(
    async ({ productId, eventType, variant, metadata = {} }) => {
      if (!user?.id) {
        // Don't track events for non-authenticated users in production
        // In development, you might want to still track with anonymous ID
        return
      }

      try {
        await eventService.trackEvent({
          userId: user.id,
          productId,
          eventType, // 'view', 'click', 'subscribe'
          variant,
          metadata,
        })
      } catch (error) {
        // Fail silently - event tracking should not disrupt user experience
        console.error('Event tracking failed:', error)
      }
    },
    [user]
  )

  const trackView = useCallback(
    (productId, variant, metadata) => {
      return trackEvent({ productId, eventType: 'view', variant, metadata })
    },
    [trackEvent]
  )

  const trackClick = useCallback(
    (productId, variant, metadata) => {
      return trackEvent({ productId, eventType: 'click', variant, metadata })
    },
    [trackEvent]
  )

  const trackSubscribe = useCallback(
    (productId, variant, metadata) => {
      return trackEvent({ productId, eventType: 'subscribe', variant, metadata })
    },
    [trackEvent]
  )

  return {
    trackEvent,
    trackView,
    trackClick,
    trackSubscribe,
  }
}

export default useEventTracking
