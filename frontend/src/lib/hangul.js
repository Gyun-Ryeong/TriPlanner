// 한글 초성 검색 도우미
const CHOSEONG = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
const HANGUL_START = 0xac00
const HANGUL_END = 0xd7a3

// '서울' → 'ㅅㅇ' (한글 음절이 아닌 글자는 그대로 둔다)
export function toChoseong(text) {
  return [...text]
    .map((ch) => {
      const code = ch.charCodeAt(0)
      if (code < HANGUL_START || code > HANGUL_END) return ch
      return CHOSEONG[Math.floor((code - HANGUL_START) / 588)]
    })
    .join('')
}

function isAllChoseong(text) {
  return text.length > 0 && [...text].every((ch) => CHOSEONG.includes(ch))
}

// 'ㅅㅇ' 같은 초성만 입력하면 초성이 앞에서부터 맞는 이름을, 그 밖의 글자를 입력하면 이름에 그 글자가 들어간 이름을 찾는다
export function matchesQuery(name, query) {
  const q = query.trim()
  if (!q) return true
  if (isAllChoseong(q)) return toChoseong(name).startsWith(q)
  return name.includes(q)
}
