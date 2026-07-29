import Layout from "@/components/Layout";
import { MedalLargeIcon } from "@/components/icons";

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
            <MedalLargeIcon size={32} className="text-brand-primary" />
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
