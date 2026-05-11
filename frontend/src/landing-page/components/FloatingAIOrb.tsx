import ParticleSphere from "../../components/agent/ParticleSphere";

const FloatingAIOrb: React.FC = () => {
  return (
    <div className="relative mx-auto flex aspect-square w-full max-w-[260px] items-center justify-center sm:max-w-[320px]">
      <div className="absolute inset-0 rounded-full bg-primary/15 blur-3xl" />
      <div className="relative size-full">
        <ParticleSphere volume={0.35} isListening={false} color="#7c3aed" isProcessing />
      </div>
      <div className="absolute bottom-3 rounded-full border bg-background/85 px-3 py-1 text-xs font-semibold text-muted-foreground shadow-sm backdrop-blur">
        AI operations agent
      </div>
    </div>
  );
};

export default FloatingAIOrb;
