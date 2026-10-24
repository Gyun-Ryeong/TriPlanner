// 화면 곳곳에서 쓰는 작은 선(stroke) 아이콘 모음. 색은 부모의 글자색(currentColor)을 따른다
function Svg({ size = 20, children, strokeWidth = 2 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

export function PinIcon(props) {
  return (
    <Svg {...props}>
      <path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </Svg>
  )
}

export function PlusIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  )
}

export function ArrowLeftIcon(props) {
  return (
    <Svg {...props}>
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </Svg>
  )
}

export function BotIcon(props) {
  return (
    <Svg {...props}>
      <rect x="4" y="8" width="16" height="12" rx="3" />
      <path d="M12 8V4M9 13v1M15 13v1M2 14h2M20 14h2" />
    </Svg>
  )
}

export function CalendarIcon(props) {
  return (
    <Svg {...props}>
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M8 3v4M16 3v4M3 10h18" />
    </Svg>
  )
}

export function BellIcon(props) {
  return (
    <Svg {...props}>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </Svg>
  )
}

export function ClipboardIcon(props) {
  return (
    <Svg {...props}>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 4h6v3H9zM9 14l2 2 4-4" />
    </Svg>
  )
}

export function PlaneIcon(props) {
  return (
    <Svg {...props}>
      <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z" />
    </Svg>
  )
}

export function MapIcon(props) {
  return (
    <Svg {...props}>
      <path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2ZM9 4v14M15 6v14" />
    </Svg>
  )
}

export function PencilIcon(props) {
  return (
    <Svg {...props}>
      <path d="M17 3a2.8 2.8 0 0 1 4 4L8 20l-5 1 1-5L17 3Z" />
    </Svg>
  )
}

export function MailIcon(props) {
  return (
    <Svg {...props}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </Svg>
  )
}

export function PhoneIcon(props) {
  return (
    <Svg {...props}>
      <rect x="7" y="2" width="10" height="20" rx="2.5" />
      <path d="M11 18h2" />
    </Svg>
  )
}

export function SendIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 19V5M5 12l7-7 7 7" />
    </Svg>
  )
}

export function CopyIcon(props) {
  return (
    <Svg {...props}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V6a2 2 0 0 1 2-2h9" />
    </Svg>
  )
}

export function CheckIcon(props) {
  return (
    <Svg {...props}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </Svg>
  )
}
