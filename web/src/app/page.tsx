import { Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-primary rounded-md flex items-center justify-center">
            <span className="text-primary-foreground font-bold text-sm">EF</span>
          </div>
          <span className="font-semibold text-lg">EventFinder AI</span>
        </div>
        <Show when="signed-out">
          <div className="flex items-center gap-2">
            <SignInButton />
            <SignUpButton />
          </div>
        </Show>
        <Show when="signed-in">
          <UserButton />
        </Show>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-6 py-24">
        <div className="max-w-2xl text-center space-y-6">
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight">
            Find events with your friends.
          </h1>
          <p className="text-lg text-muted-foreground max-w-lg mx-auto">
            Speak naturally, discover free events nearby, and let your group vote
            on the best options — all in one place.
          </p>
          <div className="flex items-center justify-center gap-4 pt-4">
            <Show when="signed-out">
              <SignInButton />
            </Show>
            <Show when="signed-in">
              <Button size="lg" onClick={() => (window.location.href = "/search")}>
                Start Searching
              </Button>
            </Show>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-20 max-w-3xl w-full">
          <FeatureCard
            icon="🎤"
            title="Voice Search"
            description="Just speak naturally. Tell us what you're looking for and we'll find it."
          />
          <FeatureCard
            icon="👥"
            title="Group Voting"
            description="Share events with friends and vote together on what to attend."
          />
          <FeatureCard
            icon="📅"
            title="Smart Scheduling"
            description="We check everyone's calendar to find times that work for the whole group."
          />
        </div>
      </main>

      <footer className="border-t border-border px-6 py-4 text-center text-sm text-muted-foreground">
        Built with Next.js, Cloudflare, and Clerk
      </footer>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: string;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center text-center p-6 rounded-lg border border-border bg-card">
      <div className="text-3xl mb-3">{icon}</div>
      <h3 className="font-semibold mb-1">{title}</h3>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  );
}
