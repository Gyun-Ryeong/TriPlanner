let loadPromise = null

export function loadNaverMapsScript(clientId) {
  if (window.naver?.maps) return Promise.resolve(window.naver)
  if (loadPromise) return loadPromise

  loadPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = `https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${clientId}`
    script.async = true
    script.onload = () => resolve(window.naver)
    script.onerror = () => {
      loadPromise = null
      reject(new Error('네이버 지도 스크립트를 불러오지 못했습니다.'))
    }
    document.head.appendChild(script)
  })

  return loadPromise
}
