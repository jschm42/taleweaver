import { ref, watch, type Ref } from 'vue'
import { useRoute, useRouter, type RouteLocationNormalizedLoaded, type Router } from 'vue-router'

export type PortalSection = 'templates' | 'sessions' | 'profile'

function parsePortalSection(section: unknown): PortalSection {
  if (section === 'profile') return 'profile'
  if (section === 'sessions') return 'sessions'
  return 'templates'
}

export interface UsePortalSectionRoutingResult {
  route: RouteLocationNormalizedLoaded
  router: Router
  activeSection: Ref<PortalSection>
  pushSection: (section: PortalSection) => void
}

export function usePortalSectionRouting(): UsePortalSectionRoutingResult {
  const router = useRouter()
  const route = useRoute()
  const activeSection = ref<PortalSection>('templates')

  watch(
    () => route.query.section,
    (section) => {
      activeSection.value = parsePortalSection(section)
    },
    { immediate: true },
  )

  /** Updates the route query to the selected portal section. */
  function pushSection(section: PortalSection) {
    router.push({ query: { ...route.query, section } })
  }

  return {
    route,
    router,
    activeSection,
    pushSection,
  }
}
