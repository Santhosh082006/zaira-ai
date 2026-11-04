import React from "react";
import { Mic, LayoutTemplate, Eye, Users, BrainCircuit } from "lucide-react";

interface CategoryData {
  score?: number | string;
  metric_name?: string;
  assessment?: string;
  evidence_observation?: string;
  what_went_well?: string;
  what_needs_improvement?: string;
  practical_recommendation?: string;
}

interface CategoryCardsProps {
  categories?: Record<string, CategoryData>;
}

export default function CategoryCards({ categories }: CategoryCardsProps) {
  const getBadgeInfo = (score: number | string | undefined) => {
    if (typeof score === "number") {
      if (score >= 85) return { badge: "Outstanding", color: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30" };
      if (score >= 75) return { badge: "Strong", color: "bg-teal-500/15 text-teal-300 border-teal-500/30" };
      if (score >= 60) return { badge: "Adequate", color: "bg-blue-500/15 text-blue-300 border-blue-500/30" };
      return { badge: "Developing", color: "bg-amber-500/15 text-amber-300 border-amber-500/30" };
    }
    return { badge: "Unmeasured", color: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30" };
  };

  const getScoreDisplay = (score: number | string | undefined) => {
    if (typeof score === "number") return score;
    return "N/A";
  };

  const speaking = categories?.speaking_style;
  const story = categories?.story_quality;
  const visual = categories?.body_language;
  const camera = categories?.engagement;
  const composure = categories?.confidence_indicators;

  const spBadge = getBadgeInfo(speaking?.score);
  const stBadge = getBadgeInfo(story?.score);
  const vsBadge = getBadgeInfo(visual?.score);
  const camBadge = getBadgeInfo(camera?.score);

  const cards = [
    {
      title: speaking?.metric_name || "Spoken Delivery",
      score: getScoreDisplay(speaking?.score),
      description: speaking?.evidence_observation || speaking?.assessment || "Acoustic speech stream not provided or unmeasured.",
      icon: <Mic className="w-4 h-4 text-emerald-400" />,
      badge: spBadge.badge,
      badgeColor: spBadge.color,
    },
    {
      title: story?.metric_name || "Narrative Detail",
      score: getScoreDisplay(story?.score),
      description: story?.evidence_observation || story?.assessment || "Missing textual narrative account. Narrative detail is unmeasured.",
      icon: <LayoutTemplate className="w-4 h-4 text-teal-400" />,
      badge: stBadge.badge,
      badgeColor: stBadge.color,
    },
    {
      title: visual?.metric_name || "Visual Presence",
      score: getScoreDisplay(visual?.score),
      description: visual?.evidence_observation || visual?.assessment || "Visual tracking returned 0 valid face frames.",
      icon: <Eye className="w-4 h-4 text-emerald-400" />,
      badge: vsBadge.badge,
      badgeColor: vsBadge.color,
    },
    {
      title: camera?.metric_name || "Camera Presence",
      score: getScoreDisplay(camera?.score),
      description: camera?.evidence_observation || camera?.assessment || "Consistent face visibility across analyzed frames (measures camera presence, not eye contact).",
      icon: <Users className="w-4 h-4 text-emerald-400" />,
      badge: camBadge.badge,
      badgeColor: camBadge.color,
    },
  ];

  // If confidence/composure was evaluated and measured, optionally add as 5th card
  if (composure && typeof composure.score === "number") {
    const compBadge = getBadgeInfo(composure.score);
    cards.push({
      title: composure.metric_name || "Delivery Composure",
      score: getScoreDisplay(composure.score),
      description: composure.evidence_observation || composure.assessment || "Delivery composure observed across behavioral channels.",
      icon: <BrainCircuit className="w-4 h-4 text-emerald-400" />,
      badge: compBadge.badge,
      badgeColor: compBadge.color,
    });
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {cards.map((card, index) => (
        <div
          key={index}
          className="bg-zinc-950/70 backdrop-blur-xl border border-white/[0.07] rounded-xl p-5 flex flex-col justify-between hover:border-white/15 transition-all"
        >
          <div>
            <div className="flex justify-between items-start mb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-white/[0.03] rounded-lg border border-white/5">
                  {card.icon}
                </div>
                <h3 className="text-sm font-semibold text-white tracking-tight">{card.title}</h3>
              </div>
              <div className="text-2xl font-mono font-bold text-white tracking-tight">
                {card.score}
              </div>
            </div>
            <p className="text-xs text-white/50 leading-relaxed mb-4">
              {card.description}
            </p>
          </div>
          <div>
            <span
              className={`inline-flex items-center text-[10px] font-mono uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${card.badgeColor}`}
            >
              {card.badge}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
