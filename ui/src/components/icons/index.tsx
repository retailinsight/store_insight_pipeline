import { useId } from "react";

export interface IconProps {
  size?: number | string;
  width?: number | string;
  height?: number | string;
  className?: string;
}

function dims(p: IconProps, dw: number | string, dh: number | string) {
  return {
    width: p.width ?? p.size ?? dw,
    height: p.height ?? p.size ?? dh,
  };
}


export function TrendUpIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 18, 10);
  return (
    <svg width={width} height={height} viewBox="0 0 20 11" fill="none" className={props.className}>
      <path d="M18.3312 0H12.4906V1.66875H17.1514L10.8219 7.99833L5.8156 2.99207L0 8.80768L1.17981 9.98748L5.8156 5.35169L10.8219 10.3579L18.3312 2.84856V7.50939H20V1.66875C20 0.748436 19.2516 0 18.3312 0Z" fill="currentColor"/>
    </svg>
  );
}

export function TrendDownIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 18, 10);
  return (
    <svg width={width} height={height} viewBox="0 0 20 11" fill="none" className={props.className}>
      <path d="M18.3312 2.84856V7.50939L10.8219 0L5.8156 5.00626L1.17981 0.370463L0 1.55027L5.8156 7.36587L10.8219 2.35962L17.1514 8.68919H12.4906V10.3579H18.3312C19.2516 10.3579 20 9.60951 20 8.68919V2.84856H18.3312Z" fill="currentColor"/>
    </svg>
  );
}

// ── KPI category icons ────────────────────────────────────────────────────

export function AvailabilityIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  const id = useId().replace(/:/g, "");
  const clipId = `avail-clip-${id}`;
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <g clipPath={`url(#${clipId})`}>
        <path d="M19.6466 5.35753L18.0549 2.71503L9.99991 0.0300293L1.94491 2.71503L0.368247 5.33086C-0.0275864 5.99086 -0.10092 6.78253 0.165747 7.50336C0.42408 8.20253 0.96908 8.74336 1.66575 8.99753L1.65908 17.2009L9.99241 19.9784L18.3257 17.2009L18.3324 8.99753C19.0374 8.75086 19.5882 8.2092 19.8482 7.50753C20.1124 6.79336 20.0391 6.01003 19.6466 5.35586V5.35753ZM14.8657 3.4092L10.0066 5.03086L5.14575 3.40503L9.99991 1.7867L14.8657 3.4092ZM1.79658 6.19003L2.87325 4.40253L8.74658 6.3667L7.47241 8.49086C7.27325 8.82253 6.85991 8.97503 6.49491 8.85253L2.26075 7.4417C2.01325 7.3592 1.81908 7.1717 1.72825 6.9267C1.63825 6.68253 1.66241 6.41253 1.79658 6.19003ZM3.33241 9.55503L5.96825 10.4334C7.08741 10.8067 8.29491 10.36 8.90241 9.34836L9.16575 8.91003L9.16158 17.9459L3.32825 16.0017L3.33325 9.55586L3.33241 9.55503ZM10.8274 17.945L10.8316 8.9042L11.0974 9.34753C11.5607 10.1209 12.3741 10.5634 13.2316 10.5634C13.4974 10.5634 13.7674 10.5209 14.0316 10.4325L16.6657 9.55503L16.6607 16L10.8274 17.945ZM18.2857 6.9317C18.1982 7.1692 18.0099 7.35086 17.7699 7.43086L13.5049 8.85253C13.1399 8.97503 12.7266 8.82336 12.5274 8.49086L11.2557 6.3717L17.1316 4.41086L18.2191 6.2167C18.3491 6.43336 18.3741 6.6942 18.2857 6.9317Z" fill="#577DF7"/>
      </g>
      <defs>
        <clipPath id={clipId}>
          <rect width="20" height="20" fill="white"/>
        </clipPath>
      </defs>
    </svg>
  );
}

export function WasteIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <path d="M18.3337 3.33333H14.167V1.66667C14.167 1.22464 13.9914 0.800716 13.6788 0.488155C13.3663 0.175595 12.9424 0 12.5003 0L7.50033 0C7.0583 0 6.63437 0.175595 6.32181 0.488155C6.00925 0.800716 5.83366 1.22464 5.83366 1.66667V3.33333H1.66699V5H3.33366V17.5C3.33366 18.163 3.59705 18.7989 4.06589 19.2678C4.53473 19.7366 5.17062 20 5.83366 20H14.167C14.83 20 15.4659 19.7366 15.9348 19.2678C16.4036 18.7989 16.667 18.163 16.667 17.5V5H18.3337V3.33333ZM7.50033 1.66667H12.5003V3.33333H7.50033V1.66667ZM15.0003 17.5C15.0003 17.721 14.9125 17.933 14.7562 18.0893C14.6 18.2455 14.388 18.3333 14.167 18.3333H5.83366C5.61264 18.3333 5.40068 18.2455 5.2444 18.0893C5.08812 17.933 5.00033 17.721 5.00033 17.5V5H15.0003V17.5Z" fill="#577DF7"/>
      <path d="M9.16667 8.33325H7.5V14.9999H9.16667V8.33325Z" fill="#577DF7"/>
      <path d="M12.5007 8.33325H10.834V14.9999H12.5007V8.33325Z" fill="#577DF7"/>
    </svg>
  );
}

// ── Hero / brand ──────────────────────────────────────────────────────────

export function MedalIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 23);
  return (
    <svg width={width} height={height} viewBox="0 0 21 24" fill="none" className={props.className}>
      <path d="M20.6971 0.938961C20.3321 0.350985 19.7001 0 19.0082 0H15.9993C14.4653 0 13.0904 0.853964 12.4124 2.22991L10.5515 6.00275C10.5305 6.00275 10.5095 5.99975 10.4885 5.99975C10.4745 5.99975 10.4615 6.00175 10.4475 6.00175L8.58659 2.22991C7.90762 0.853964 6.53368 0 4.99974 0H1.99087C1.29889 0 0.666921 0.350985 0.300936 0.938961C-0.0640485 1.52694 -0.0990471 2.24891 0.20694 2.86988L3.43881 9.42261C2.22186 10.9575 1.48889 12.8935 1.48889 15.0004C1.48889 19.9622 5.52672 24 10.4885 24C15.4503 24 19.4881 19.9622 19.4881 15.0004C19.4881 12.9015 18.7602 10.9735 17.5512 9.44061L20.7921 2.87088C21.0991 2.24991 21.0631 1.52794 20.6981 0.939961L20.6971 0.938961ZM4.99874 1.99992C5.76571 1.99992 6.45268 2.4269 6.79167 3.11487L8.3466 6.26774C7.08265 6.57773 5.9227 7.1517 4.93074 7.93367L1.98987 1.99992H4.99874ZM10.4875 21.9991C6.62767 21.9991 3.4878 18.8592 3.4878 14.9994C3.4878 11.3395 6.31269 8.33165 9.89654 8.02967C9.89754 8.02967 9.89854 8.02967 9.90054 8.02967C10.0945 8.01367 10.2905 7.99967 10.4885 7.99967C14.3484 7.99967 17.4882 11.1395 17.4882 14.9994C17.4882 18.8592 14.3484 21.9991 10.4885 21.9991H10.4875ZM16.0573 7.94467C15.0673 7.1607 13.9094 6.58573 12.6474 6.27274L14.2054 3.11487C14.5443 2.4269 15.2313 1.99992 15.9983 1.99992L18.9982 1.98492L16.0573 7.94467ZM14.6443 14.4094C14.6443 14.7704 14.3933 15.0744 14.1054 15.2344L12.6154 16.0623L13.2764 17.8653C13.4044 18.2142 13.2884 18.6062 12.9914 18.8302C12.6874 19.0592 12.2684 19.0562 11.9685 18.8232L10.4865 17.6773L9.00457 18.8232C8.70359 19.0552 8.2846 19.0582 7.98162 18.8302C7.68463 18.6062 7.56863 18.2152 7.69663 17.8653L8.3576 16.0623L6.86766 15.2344C6.57968 15.0744 6.32869 14.7704 6.32869 14.4094C6.32869 14.1034 6.59467 13.7654 7.02466 13.7654H9.16457L9.73154 11.5905C9.82154 11.2455 10.1305 11.0055 10.4865 10.9995C10.8415 11.0065 11.1515 11.2455 11.2415 11.5905L11.8085 13.7654H13.9484C14.3784 13.7654 14.6443 14.1024 14.6443 14.4094Z" fill="#577DF7"/>
    </svg>
  );
}

export function MedalLargeIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 26, 30);
  return (
    <svg width={width} height={height} viewBox="0 0 32 37" fill="none" className={props.className}>
      <path d="M31.5393 1.44756C30.9831 0.541102 30.0201 0 28.9656 0H24.3805C22.043 0 19.9478 1.31653 18.9147 3.43777L16.0789 9.25424C16.0469 9.25424 16.0149 9.24961 15.9829 9.24961C15.9616 9.24961 15.9418 9.2527 15.9205 9.2527L13.0847 3.43777C12.05 1.31653 9.95635 0 7.61886 0H3.03378C1.97932 0 1.01629 0.541102 0.458582 1.44756C-0.0976004 2.35403 -0.150933 3.46706 0.315346 4.4244L5.24023 14.5265C3.38578 16.8929 2.26884 19.8774 2.26884 23.1256C2.26884 30.775 8.4219 37 15.9829 37C23.544 37 29.697 30.775 29.697 23.1256C29.697 19.8898 28.5877 16.9175 26.7454 14.5543L31.684 4.42594C32.1518 3.46861 32.097 2.35557 31.5408 1.44911L31.5393 1.44756ZM7.61734 3.0832C8.78608 3.0832 9.83292 3.74147 10.3495 4.80209L12.719 9.66276C10.7929 10.1407 9.02531 11.0255 7.51372 12.2311L3.03226 3.0832H7.61734ZM15.9814 33.9153C10.0996 33.9153 5.31489 29.0746 5.31489 23.124C5.31489 17.4818 9.61959 12.8446 15.0808 12.3791C15.0824 12.3791 15.0839 12.3791 15.0869 12.3791C15.3826 12.3544 15.6812 12.3328 15.9829 12.3328C21.8647 12.3328 26.6494 17.1735 26.6494 23.124C26.6494 29.0746 21.8647 33.9153 15.9829 33.9153H15.9814ZM24.4689 12.248C22.9604 11.0394 21.1958 10.153 19.2728 9.67047L21.6468 4.80209C22.1634 3.74147 23.2103 3.0832 24.379 3.0832L28.9504 3.06008L24.4689 12.248Z" fill="currentColor"/>
    </svg>
  );
}

export function LightningIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 24 24" fill="none" className={props.className}>
      <path d="M12.5658 24H8.71882L10.7188 16H6.58582C6.18639 15.9998 5.79255 15.9062 5.43575 15.7267C5.07894 15.5472 4.76908 15.2867 4.53092 14.966C4.29276 14.6454 4.13291 14.2734 4.06413 13.88C3.99535 13.4865 4.01956 13.0824 4.13482 12.7L7.97582 0H17.4428L14.4428 8H18.4658C18.9235 8.00029 19.3726 8.1246 19.7653 8.35972C20.1581 8.59484 20.4797 8.93197 20.6962 9.33529C20.9126 9.73861 21.0157 10.193 20.9945 10.6503C20.9733 11.1075 20.8286 11.5504 20.5758 11.932L12.5658 24ZM11.2808 22H11.4928L18.9088 10.826C18.962 10.7459 18.9924 10.6528 18.9969 10.5568C19.0013 10.4607 18.9797 10.3653 18.9343 10.2806C18.8888 10.1958 18.8213 10.125 18.7388 10.0756C18.6563 10.0262 18.562 10.0001 18.4658 10H11.5568L14.5568 2H9.45982L6.04882 13.276C6.02336 13.3599 6.01789 13.4485 6.03286 13.5348C6.04784 13.6212 6.08283 13.7028 6.13503 13.7732C6.18724 13.8436 6.2552 13.9008 6.33348 13.9401C6.41177 13.9795 6.49819 14 6.58582 14H13.2858L11.2808 22Z" fill="#577DF7"/>
    </svg>
  );
}

// ── Calendar variants ─────────────────────────────────────────────────────

export function CalendarDotsIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <path fillRule="evenodd" clipRule="evenodd" d="M5.33375 17.9995C3.49407 17.9977 2.0018 16.5064 2 14.6668V6.66674C2.0018 4.82714 3.49407 3.33494 5.33375 3.33314H5.99977V2.66714C5.99977 2.29814 6.29949 2.00024 6.6667 2.00024C7.03482 2.00024 7.33453 2.29814 7.33453 2.66714V3.33314H12.6673V2.66714C12.6673 2.29814 12.9652 2.00024 13.3342 2.00024C13.7023 2.00024 14.0002 2.29814 14.0002 2.66714V3.33314H14.6672C16.5068 3.33494 17.9982 4.82714 18 6.66674V14.6668C17.9982 16.5064 16.5068 17.9977 14.6672 17.9995H5.33375ZM3.33386 14.6668C3.33386 15.7711 4.2294 16.6666 5.33375 16.6666H14.6672C15.7724 16.6666 16.667 15.7711 16.667 14.6668V8.66744H3.33386V14.6668ZM3.33386 6.66674V7.33274H16.667V6.66674C16.667 5.56244 15.7724 4.66694 14.6672 4.66694H5.33375C4.2294 4.66694 3.33386 5.56244 3.33386 6.66674ZM12.3343 12.0001C12.3343 11.4475 12.7816 11.0002 13.3342 11.0002C13.8859 11.0002 14.3341 11.4475 14.3341 12.0001C14.3341 12.5518 13.8859 13 13.3342 13C12.7816 13 12.3343 12.5518 12.3343 12.0001ZM9.00051 12.0001C9.00051 11.4475 9.44783 11.0002 10.0005 11.0002C10.5531 11.0002 11.0004 11.4475 11.0004 12.0001C11.0004 12.5518 10.5531 13 10.0005 13C9.44783 13 9.00051 12.5518 9.00051 12.0001ZM5.66676 12.0001C5.66676 11.4475 6.11498 11.0002 6.6667 11.0002C7.21933 11.0002 7.66665 11.4475 7.66665 12.0001C7.66665 12.5518 7.21933 13 6.6667 13C6.11498 13 5.66676 12.5518 5.66676 12.0001Z" fill="currentColor"/>
    </svg>
  );
}

export function CalendarIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <rect x="3" y="4" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M3 8h14M7 2v4M13 2v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

// ── Checks ─────────────────────────────────────────────────────────────────

export function CheckIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <path d="M16.8609 4.19619L7.64819 13.4082C7.58625 13.4704 7.51264 13.5197 7.43159 13.5534C7.35053 13.5871 7.26363 13.6044 7.17586 13.6044C7.08809 13.6044 7.00118 13.5871 6.92013 13.5534C6.83908 13.5197 6.76547 13.4704 6.70353 13.4082L3.14086 9.84219C2.99963 9.70097 2.92058 9.50937 2.92058 9.30975C2.92058 9.11013 2.99963 8.91853 3.14086 8.7773C3.28208 8.63608 3.47369 8.55703 3.67331 8.55703C3.87292 8.55703 4.06453 8.63608 4.20575 8.7773L7.17586 11.7481L15.7961 3.12784C15.9374 2.98661 16.129 2.90756 16.3286 2.90756C16.5282 2.90756 16.7198 2.98661 16.8609 3.12784C17.0021 3.26907 17.0812 3.46067 17.0812 3.66029C17.0812 3.85991 17.0021 4.05151 16.8609 4.19274V4.19619Z" fill="currentColor"/>
    </svg>
  );
}

export function CheckBoldIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <path d="M16.8609 4.19619L7.64819 13.4082C7.58625 13.4704 7.51264 13.5197 7.43159 13.5534C7.35053 13.5871 7.26363 13.6044 7.17586 13.6044C7.08809 13.6044 7.00118 13.5871 6.92013 13.5534C6.83908 13.5197 6.76547 13.4704 6.70353 13.4082L3.14086 9.84219C3.07892 9.78001 3.00531 9.73067 2.92426 9.697C2.8432 9.66333 2.7563 9.646 2.66853 9.646C2.58076 9.646 2.49385 9.66333 2.4128 9.697C2.33174 9.73067 2.25813 9.78001 2.19619 9.84219C2.13401 9.90413 2.08467 9.97774 2.051 10.0588C2.01733 10.1399 2 10.2268 2 10.3145C2 10.4023 2.01733 10.4892 2.051 10.5703C2.08467 10.6513 2.13401 10.7249 2.19619 10.7869L5.76019 14.3502C6.13616 14.7255 6.64566 14.9362 7.17686 14.9362C7.70806 14.9362 8.21756 14.7255 8.59353 14.3502L17.8055 5.14019C17.8676 5.07827 17.9169 5.0047 17.9505 4.9237C17.9841 4.84271 18.0014 4.75588 18.0014 4.66819C18.0014 4.5805 17.9841 4.49367 17.9505 4.41268C17.9169 4.33169 17.8676 4.25812 17.8055 4.19619C17.7436 4.13401 17.67 4.08467 17.5889 4.051C17.5079 4.01733 17.421 4 17.3332 4C17.2454 4 17.1585 4.01733 17.0775 4.051C16.9964 4.08467 16.9228 4.13401 16.8609 4.19619Z" fill="currentColor"/>
    </svg>
  );
}

// ── Smart-actions controls ────────────────────────────────────────────────

export function BoardViewIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 24 24" fill="none" className={props.className}>
      <path d="M3 3H9V9H3V3ZM11 3H17V9H11V3ZM15 11H17V17H15V11ZM3 11H9V17H3V11ZM11 15H13V17H11V15Z" fill="currentColor" stroke="currentColor" strokeWidth="0.5"/>
    </svg>
  );
}

export function ListViewIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 24 24" fill="none" className={props.className}>
      <path d="M3 4H21V6H3V4ZM3 10H21V12H3V10ZM3 16H21V18H3V16Z" fill="currentColor"/>
    </svg>
  );
}

export function ExpandIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 16, 16);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <path d="M11 3h6v6M17 3l-8 8M8 5H4a1 1 0 00-1 1v10a1 1 0 001 1h10a1 1 0 001-1v-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// ── Close / X ──────────────────────────────────────────────────────────────

export function CloseIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 16, 16);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <path d="M17.805 2.197a.75.75 0 00-1.061 0L10 8.94 3.256 2.197a.75.75 0 00-1.061 1.06L8.94 10l-6.744 6.743a.75.75 0 001.06 1.061L10 11.06l6.744 6.744a.75.75 0 001.06-1.06L11.06 10l6.744-6.744a.75.75 0 000-1.06z" fill="currentColor"/>
    </svg>
  );
}

export function CloseStrokeIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 18, 18);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className={props.className}>
      <line x1="4" y1="4" x2="16" y2="16"/>
      <line x1="16" y1="4" x2="4" y2="16"/>
    </svg>
  );
}

// ── KPI Detail Panel section icons ────────────────────────────────────────

export function ChartBarIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <path d="M2 2v16h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M6 14v-4M10 14V8M14 14v-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function DocumentIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <path d="M4 4a2 2 0 012-2h4.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M7 10h6M7 13h6M7 7h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function TrendingIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <path d="M3 14l4-4 3 3 7-7m0 0h-5m5 0v5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function GridIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <path d="M3 3h6v6H3V3zm0 8h6v6H3v-6zm8-8h6v6h-6V3zm0 8h6v6h-6v-6z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function ClockIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M10 6v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function TargetIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="10" cy="10" r="4" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="10" cy="10" r="1.5" fill="currentColor"/>
    </svg>
  );
}

export function LightBulbIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 20, 20);
  return (
    <svg width={width} height={height} viewBox="0 0 20 20" fill="none" className={props.className}>
      <path d="M10 2a6 6 0 014 10.5V14a2 2 0 01-2 2h-4a2 2 0 01-2-2v-1.5A6 6 0 0110 2z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M8 16h4M10 2v1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

// ── Navigation sidebar ────────────────────────────────────────────────────

export function DashboardIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 28, 28);
  return (
    <svg width={width} height={height} viewBox="0 0 32 32" fill="none" className={props.className}>
      <path d="M2.66667 14.6667H17.3333C18.0406 14.6667 18.7189 14.3857 19.219 13.8856C19.719 13.3855 20 12.7072 20 12V2.66667C20 1.95942 19.719 1.28115 19.219 0.781049C18.7189 0.280952 18.0406 0 17.3333 0L2.66667 0C1.95942 0 1.28115 0.280952 0.781049 0.781049C0.280952 1.28115 0 1.95942 0 2.66667L0 12C0 12.7072 0.280952 13.3855 0.781049 13.8856C1.28115 14.3857 1.95942 14.6667 2.66667 14.6667ZM2.66667 2.66667H17.3333V12H2.66667V2.66667Z" fill="currentColor"/>
      <path d="M29.3332 0H25.3332C24.6259 0 23.9477 0.280952 23.4476 0.781049C22.9475 1.28115 22.6665 1.95942 22.6665 2.66667V12C22.6665 12.7072 22.9475 13.3855 23.4476 13.8856C23.9477 14.3857 24.6259 14.6667 25.3332 14.6667H29.3332C30.0404 14.6667 30.7187 14.3857 31.2188 13.8856C31.7189 13.3855 31.9998 12.7072 31.9998 12V2.66667C31.9998 1.95942 31.7189 1.28115 31.2188 0.781049C30.7187 0.280952 30.0404 0 29.3332 0ZM29.3332 12H25.3332V2.66667H29.3332V12Z" fill="currentColor"/>
      <path d="M6.66667 17.3333H2.66667C1.95942 17.3333 1.28115 17.6142 0.781049 18.1143C0.280952 18.6144 0 19.2927 0 19.9999L0 29.3333C0 30.0405 0.280952 30.7188 0.781049 31.2189C1.28115 31.719 1.95942 31.9999 2.66667 31.9999H6.66667C7.37391 31.9999 8.05219 31.719 8.55229 31.2189C9.05238 30.7188 9.33333 30.0405 9.33333 29.3333V19.9999C9.33333 19.2927 9.05238 18.6144 8.55229 18.1143C8.05219 17.6142 7.37391 17.3333 6.66667 17.3333ZM6.66667 29.3333H2.66667V19.9999H6.66667V29.3333Z" fill="currentColor"/>
      <path d="M29.3333 17.3333H14.6667C13.9594 17.3333 13.2811 17.6142 12.781 18.1143C12.281 18.6144 12 19.2927 12 19.9999V29.3333C12 30.0405 12.281 30.7188 12.781 31.2189C13.2811 31.719 13.9594 31.9999 14.6667 31.9999H29.3333C30.0406 31.9999 30.7189 31.719 31.219 31.2189C31.719 30.7188 32 30.0405 32 29.3333V19.9999C32 19.2927 31.719 18.6144 31.219 18.1143C30.7189 17.6142 30.0406 17.3333 29.3333 17.3333ZM29.3333 29.3333H14.6667V19.9999H29.3333V29.3333Z" fill="currentColor"/>
    </svg>
  );
}

export function SmartActionsIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 28, 28);
  return (
    <svg width={width} height={height} viewBox="0 0 32 32" fill="none" className={props.className}>
      <path d="M16.7548 32H11.6254L14.2921 21.3333H8.78142C8.24885 21.3331 7.72372 21.2083 7.24799 20.9689C6.77225 20.7296 6.3591 20.3822 6.04156 19.9547C5.72401 19.5271 5.51087 19.0313 5.41917 18.5066C5.32746 17.982 5.35974 17.4432 5.51342 16.9333L10.6348 0H23.2574L19.2574 10.6667H24.6214C25.2317 10.6671 25.8305 10.8328 26.3541 11.1463C26.8777 11.4598 27.3066 11.9093 27.5952 12.4471C27.8838 12.9848 28.0212 13.5907 27.993 14.2003C27.9647 14.81 27.7718 15.4006 27.4348 15.9093L16.7548 32ZM15.0414 29.3333H15.3241L25.2121 14.4347C25.2829 14.3278 25.3235 14.2038 25.3295 14.0757C25.3354 13.9477 25.3066 13.8204 25.246 13.7074C25.1854 13.5944 25.0954 13.5 24.9854 13.4341C24.8754 13.3683 24.7496 13.3334 24.6214 13.3333H15.4094L19.4094 2.66667H12.6134L8.06542 17.7013C8.03147 17.8131 8.02418 17.9313 8.04414 18.0465C8.06411 18.1616 8.11076 18.2704 8.18037 18.3643C8.24997 18.4581 8.3406 18.5344 8.44497 18.5869C8.54935 18.6394 8.66458 18.6667 8.78142 18.6667H17.7148L15.0414 29.3333Z" fill="currentColor"/>
    </svg>
  );
}

export function LogoutIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 26, 26);
  return (
    <svg width={width} height={height} viewBox="0 0 32 32" fill="none" className={props.className}>
      <path d="M27.5511 12.9834L23.4135 8.84582C23.2124 8.65152 22.9429 8.544 22.6632 8.54643C22.3836 8.54886 22.116 8.66104 21.9183 8.85881C21.7205 9.05658 21.6083 9.32411 21.6059 9.60379C21.6034 9.88347 21.711 10.1529 21.9053 10.3541L26.0429 14.4917C26.1658 14.617 26.2732 14.7567 26.3629 14.9077C26.3469 14.9077 26.3341 14.8992 26.3181 14.8992L9.58846 14.9333C9.30556 14.9333 9.03425 15.0457 8.83421 15.2457C8.63418 15.4457 8.52179 15.7171 8.52179 16C8.52179 16.2828 8.63418 16.5542 8.83421 16.7542C9.03425 16.9542 9.30556 17.0666 9.58846 17.0666L26.3117 17.0325C26.3415 17.0325 26.3661 17.0176 26.3949 17.0154C26.3002 17.1959 26.1803 17.3618 26.0386 17.5082L21.901 21.6458C21.7068 21.8419 21.5985 22.1072 21.5998 22.3834C21.6011 22.6596 21.7119 22.9238 21.9079 23.118C22.104 23.3122 22.3693 23.4198 22.6455 23.4184C22.9217 23.417 23.1859 23.3065 23.3801 23.1105L27.5177 18.973C28.3175 18.1729 28.7669 17.0878 28.7669 15.9564C28.7669 14.825 28.3175 13.7399 27.5177 12.9398L27.5511 12.9834Z" fill="currentColor"/>
      <path d="M10.6669 26.6666H8.53353C7.68484 26.6666 6.8709 26.3295 6.27079 25.7294C5.67067 25.1292 5.33353 24.3153 5.33353 23.4666V8.53328C5.33353 7.68459 5.67067 6.87066 6.27079 6.27054C6.8709 5.67043 7.68484 5.33328 8.53353 5.33328H10.6669C10.9498 5.33328 11.2211 5.2209 11.4211 5.02087C11.6211 4.82083 11.7335 4.54952 11.7335 4.26662C11.7335 3.98372 11.6211 3.71241 11.4211 3.51237C11.2211 3.31233 10.9498 3.19995 10.6669 3.19995H8.53353C7.11956 3.20164 5.76399 3.76409 4.76416 4.76392C3.76434 5.76375 3.20189 7.11932 3.2002 8.53328L3.2002 23.4666C3.20189 24.8806 3.76434 26.2362 4.76416 27.236C5.76399 28.2358 7.11956 28.7983 8.53353 28.8H10.6669C10.9498 28.8 11.2211 28.6876 11.4211 28.4875C11.6211 28.2875 11.7335 28.0162 11.7335 27.7333C11.7335 27.4504 11.6211 27.1791 11.4211 26.979C11.2211 26.779 10.9498 26.6666 10.6669 26.6666Z" fill="currentColor"/>
    </svg>
  );
}

export function SunIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 22, 22);
  return (
    <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={props.className}>
      <circle cx="12" cy="12" r="4"/>
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
    </svg>
  );
}

export function MoonIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 22, 22);
  return (
    <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={props.className}>
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  );
}

export function HamburgerIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 22, 22);
  return (
    <svg width={width} height={height} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={props.className}>
      <line x1="3" y1="6" x2="21" y2="6"/>
      <line x1="3" y1="12" x2="21" y2="12"/>
      <line x1="3" y1="18" x2="21" y2="18"/>
    </svg>
  );
}

/** StoreInsight wordmark / cart logo. */
export function LogoIcon(props: IconProps = {}) {
  const { width, height } = dims(props, 28, 24);
  return (
    <svg width={width} height={height} viewBox="0 0 35 30" fill="none" xmlns="http://www.w3.org/2000/svg" className={props.className}>
      <path d="M1 1H5.5L8.5 18H27.5L31 6H11" stroke="#577DF7" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="12" cy="24" r="2.5" fill="#577DF7"/>
      <circle cx="24" cy="24" r="2.5" fill="#577DF7"/>
    </svg>
  );
}
