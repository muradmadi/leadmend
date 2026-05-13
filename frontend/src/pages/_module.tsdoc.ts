/**
 * @packageDocumentation
 * Route definitions and page layouts for the LeadMend application.
 * 
 * @remarks
 * This directory utilizes Astro's file-based routing to define the application's 
 * entry points. It serves as the orchestration layer between the static 
 * SEO-optimized shell and interactive React components.
 * 
 * The architecture prioritizes:
 * 1. **SSR Efficiency:** Leveraging Astro for fast initial loads.
 * 2. **Islands Architecture:** Selectively hydrating interactive components 
 *    (like the Lead Demo) to minimize JavaScript shipping to the client.
 */
