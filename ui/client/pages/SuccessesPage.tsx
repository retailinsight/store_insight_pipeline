import Layout from "@/components/Layout";

function MedalIcon() {
  return (
    <svg width="32" height="37" viewBox="0 0 32 37" fill="none">
      <path d="M31.5393 1.44756C30.9831 0.541102 30.0201 0 28.9656 0H24.3805C22.043 0 19.9478 1.31653 18.9147 3.43777L16.0789 9.25424C16.0469 9.25424 16.0149 9.24961 15.9829 9.24961C15.9616 9.24961 15.9418 9.2527 15.9205 9.2527L13.0847 3.43777C12.05 1.31653 9.95635 0 7.61886 0H3.03378C1.97932 0 1.01629 0.541102 0.458582 1.44756C-0.0976004 2.35403 -0.150933 3.46706 0.315346 4.4244L5.24023 14.5265C3.38578 16.8929 2.26884 19.8774 2.26884 23.1256C2.26884 30.775 8.4219 37 15.9829 37C23.544 37 29.697 30.775 29.697 23.1256C29.697 19.8898 28.5877 16.9175 26.7454 14.5543L31.684 4.42594C32.1518 3.46861 32.097 2.35557 31.5408 1.44911L31.5393 1.44756Z" fill="#577DF7"/>
    </svg>
  );
}

export default function SuccessesPage() {
  return (
    <Layout>
      <div className="px-8 pt-6 pb-4 shrink-0">
        <h1 className="font-bebas text-4xl text-black dark:text-white tracking-wide">
          Store Successes
        </h1>
      </div>
      <div className="flex-1 flex items-center justify-center px-8 pb-8">
        <div className="flex flex-col items-center gap-6 text-center max-w-sm">
          <div className="flex items-center justify-center w-20 h-20 rounded-2xl bg-brand-primary-100">
            <MedalIcon />
          </div>
          <div>
            <h2 className="font-bebas text-3xl text-black dark:text-white tracking-wide mb-2">
              Store Successes
            </h2>
            <p className="font-dm-sans text-sm text-gray-500 dark:text-white/60 leading-relaxed">
              The full Successes view is coming soon. Your recent wins are showcased on the{" "}
              <strong className="text-brand-primary">Dashboard</strong>.
            </p>
          </div>
          <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-app-lime font-dm-sans text-sm text-black">
            3 recent successes worth £10,500
          </div>
        </div>
      </div>
    </Layout>
  );
}
