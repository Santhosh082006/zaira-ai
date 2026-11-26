/**
 * English Grapheme-to-Phoneme (G2P) -> Viseme Synchronization Engine for Zaira 3D Avatar.
 *
 * Converts Edge-TTS WordBoundary timings (`offset_ms`, `duration_ms`, `word`) into
 * a continuous coarticulated ARKit + Oculus viseme timeline (`viseme_PP`, `viseme_FF`,
 * `viseme_TH`, `viseme_DD`, `viseme_kk`, `viseme_nn`, `viseme_RR`, `viseme_SS`,
 * `viseme_CH`, `viseme_aa`, `viseme_E`, `viseme_I`, `viseme_O`, `viseme_U`, `jawOpen`,
 * `mouthClose`, `mouthPressLeft/Right`, `mouthPucker`, `mouthFunnel`, `mouthStretchLeft/Right`).
 */

export interface WordTiming {
  word: string;
  offset_ms: number;
  duration_ms: number;
}

export type VisemeKey =
  | "viseme_sil"
  | "viseme_PP"
  | "viseme_FF"
  | "viseme_TH"
  | "viseme_DD"
  | "viseme_kk"
  | "viseme_nn"
  | "viseme_RR"
  | "viseme_SS"
  | "viseme_CH"
  | "viseme_aa"
  | "viseme_E"
  | "viseme_I"
  | "viseme_O"
  | "viseme_U"
  | "jawOpen"
  | "mouthClose"
  | "mouthPressLeft"
  | "mouthPressRight"
  | "mouthPucker"
  | "mouthFunnel"
  | "mouthRollLower"
  | "mouthStretchLeft"
  | "mouthStretchRight";

export type VisemePose = Partial<Record<VisemeKey, number>>;

export interface PhonemeFrame {
  phoneme: string;
  start_ms: number;
  end_ms: number;
  isBilabial: boolean;
  pose: VisemePose;
}

const PHONEME_POSES: Record<string, { pose: VisemePose; weight: number; bilabial?: boolean }> = {
  // Bilabial stops/nasal: M, B, P -> strict lip closure & zero jaw open
  PP: {
    weight: 0.75,
    bilabial: true,
    pose: {
      viseme_PP: 0.88,
      mouthClose: 0.32,
      mouthPressLeft: 0.28,
      mouthPressRight: 0.28,
      jawOpen: 0.0,
    },
  },
  // Labiodentals: F, V -> distinct lower-lip tuck up toward upper teeth
  FF: {
    weight: 0.90,
    pose: {
      viseme_FF: 0.78,
      mouthRollLower: 0.36,
      mouthClose: 0.16,
      jawOpen: 0.01,
    },
  },
  // Interdentals: TH
  TH: {
    weight: 0.85,
    pose: {
      viseme_TH: 0.48,
      jawOpen: 0.03,
    },
  },
  // Alveolar stops / lateral: T, D, L
  DD: {
    weight: 0.72,
    pose: {
      viseme_DD: 0.40,
      jawOpen: 0.04,
    },
  },
  // Alveolar nasal: N
  NN: {
    weight: 0.72,
    pose: {
      viseme_nn: 0.40,
      jawOpen: 0.03,
    },
  },
  // Velar stops: K, G
  KK: {
    weight: 0.72,
    pose: {
      viseme_kk: 0.42,
      jawOpen: 0.04,
    },
  },
  // Sibilants: S, Z
  SS: {
    weight: 0.9,
    pose: {
      viseme_SS: 0.52,
      mouthStretchLeft: 0.12,
      mouthStretchRight: 0.12,
      jawOpen: 0.02,
    },
  },
  // Post-alveolar / affricates: SH, CH, JH, ZH
  CH: {
    weight: 0.9,
    pose: {
      viseme_CH: 0.54,
      mouthFunnel: 0.18,
      jawOpen: 0.03,
    },
  },
  // Rhotic: R, ER
  RR: {
    weight: 0.95,
    pose: {
      viseme_RR: 0.46,
      mouthFunnel: 0.16,
      jawOpen: 0.04,
    },
  },
  // Rounded glide/high-back vowel: W, UW, UH
  U: {
    weight: 1.35,
    pose: {
      viseme_U: 0.54,
      mouthPucker: 0.34,
      mouthFunnel: 0.16,
      jawOpen: 0.03,
    },
  },
  // Open-mid rounded vowel: OW, AO
  O: {
    weight: 1.45,
    pose: {
      viseme_O: 0.46,
      mouthFunnel: 0.22,
      mouthPucker: 0.14,
      jawOpen: 0.05,
    },
  },
  // Open unrounded vowels: AA, AH, AE (avoid over-opening lower jaw/teeth)
  AA: {
    weight: 1.45,
    pose: {
      viseme_aa: 0.28,
      jawOpen: 0.06,
    },
  },
  // Mid front spread vowel: EH, EY
  E: {
    weight: 1.35,
    pose: {
      viseme_E: 0.34,
      mouthStretchLeft: 0.14,
      mouthStretchRight: 0.14,
      jawOpen: 0.04,
    },
  },
  // High front spread vowel: IY, IH
  I: {
    weight: 1.3,
    pose: {
      viseme_I: 0.36,
      mouthStretchLeft: 0.16,
      mouthStretchRight: 0.16,
      jawOpen: 0.03,
    },
  },
};

/**
 * Convert an English word into an ordered sequence of viseme phoneme tokens.
 */
export function wordToPhonemes(rawWord: string): string[] {
  const clean = rawWord.toLowerCase().replace(/[^a-z]/g, "");
  if (!clean) return [];

  // Common irregular/high-frequency interview words for clean pronunciation mapping
  const lexicon: Record<string, string[]> = {
    i: ["AA", "I"],
    a: ["AA"],
    the: ["TH", "AA"],
    you: ["I", "U"],
    your: ["I", "O", "RR"],
    are: ["AA", "RR"],
    to: ["DD", "U"],
    of: ["AA", "FF"],
    and: ["AA", "NN", "DD"],
    in: ["I", "NN"],
    is: ["I", "SS"],
    for: ["FF", "O", "RR"],
    with: ["U", "I", "TH"],
    on: ["AA", "NN"],
    we: ["U", "I"],
    be: ["PP", "I"],
    am: ["AA", "PP"],
    ai: ["E", "I"],
    zaira: ["SS", "AA", "I", "RR", "AA"],
    api: ["E", "PP", "I", "AA", "I"],
    apis: ["E", "PP", "I", "AA", "I", "SS"],
    sql: ["SS", "I", "KK", "U", "AA", "DD"],
    hello: ["AA", "E", "DD", "O"],
    welcome: ["U", "E", "DD", "KK", "AA", "PP"],
    walk: ["U", "O", "KK"],
    through: ["TH", "RR", "U"],
    what: ["U", "AA", "DD"],
    would: ["U", "DD"],
    could: ["KK", "U", "DD"],
    should: ["CH", "U", "DD"],
    people: ["PP", "I", "PP", "DD"],
    problem: ["PP", "RR", "O", "PP", "DD", "AA", "PP"],
    build: ["PP", "I", "DD", "DD"],
    built: ["PP", "I", "DD", "DD"],
    experience: ["E", "KK", "SS", "PP", "I", "RR", "I", "AA", "NN", "SS"],
    interview: ["I", "NN", "DD", "RR", "FF", "I", "U"],
    software: ["SS", "O", "FF", "DD", "U", "E", "RR"],
    engineering: ["E", "NN", "CH", "AA", "NN", "I", "RR", "I", "NN", "KK"],
    architecture: ["AA", "RR", "KK", "AA", "DD", "E", "KK", "CH", "RR"],
  };
  if (lexicon[clean]) {
    return lexicon[clean];
  }

  // Silent trailing 'e' check (e.g. "make", "code", "time")
  const hasSilentE =
    clean.length > 2 &&
    clean.endsWith("e") &&
    !"aeiouy".includes(clean[clean.length - 2]) &&
    !clean.endsWith("le");

  const chars = hasSilentE ? clean.slice(0, -1) : clean;
  const out: string[] = [];
  let i = 0;

  const pushUnique = (ph: string) => {
    if (out[out.length - 1] !== ph) {
      out.push(ph);
    }
  };

  while (i < chars.length) {
    const rest = chars.slice(i);

    // 4-char & 3-char patterns
    if (rest.startsWith("tion") || rest.startsWith("sion")) {
      pushUnique("CH");
      pushUnique("AA");
      pushUnique("NN");
      i += 4;
      continue;
    }
    if (rest.startsWith("tch")) {
      pushUnique("CH");
      i += 3;
      continue;
    }
    if (rest.startsWith("igh")) {
      pushUnique("AA");
      pushUnique("I");
      i += 3;
      continue;
    }

    // 2-char digraphs
    if (rest.startsWith("ch") || rest.startsWith("sh") || rest.startsWith("dg")) {
      pushUnique("CH");
      i += 2;
      continue;
    }
    if (rest.startsWith("th")) {
      pushUnique("TH");
      i += 2;
      continue;
    }
    if (rest.startsWith("ph")) {
      pushUnique("FF");
      i += 2;
      continue;
    }
    if (rest.startsWith("wh")) {
      pushUnique("U");
      i += 2;
      continue;
    }
    if (rest.startsWith("qu")) {
      pushUnique("KK");
      pushUnique("U");
      i += 2;
      continue;
    }
    if (rest.startsWith("ng")) {
      pushUnique("NN");
      pushUnique("KK");
      i += 2;
      continue;
    }
    if (rest.startsWith("ck")) {
      pushUnique("KK");
      i += 2;
      continue;
    }
    if (rest.startsWith("ee") || rest.startsWith("ea") || rest.startsWith("ie")) {
      pushUnique("I");
      i += 2;
      continue;
    }
    if (rest.startsWith("oo")) {
      pushUnique("U");
      i += 2;
      continue;
    }
    if (rest.startsWith("ou") || rest.startsWith("ow")) {
      pushUnique("O");
      pushUnique("U");
      i += 2;
      continue;
    }
    if (rest.startsWith("oa") || rest.startsWith("oe")) {
      pushUnique("O");
      i += 2;
      continue;
    }
    if (rest.startsWith("ai") || rest.startsWith("ay") || rest.startsWith("ei") || rest.startsWith("ey")) {
      pushUnique("E");
      pushUnique("I");
      i += 2;
      continue;
    }
    if (rest.startsWith("oi") || rest.startsWith("oy")) {
      pushUnique("O");
      pushUnique("I");
      i += 2;
      continue;
    }
    if (rest.startsWith("au") || rest.startsWith("aw")) {
      pushUnique("O");
      i += 2;
      continue;
    }
    if (rest.startsWith("er") || rest.startsWith("ir") || rest.startsWith("ur")) {
      pushUnique("RR");
      i += 2;
      continue;
    }
    if (rest.startsWith("ar")) {
      pushUnique("AA");
      pushUnique("RR");
      i += 2;
      continue;
    }
    if (rest.startsWith("or")) {
      pushUnique("O");
      pushUnique("RR");
      i += 2;
      continue;
    }

    // Single letters
    const ch = chars[i];
    const next = chars[i + 1] || "";

    if (ch === "m" || ch === "b" || ch === "p") {
      pushUnique("PP");
    } else if (ch === "f" || ch === "v") {
      pushUnique("FF");
    } else if (ch === "s" || ch === "z") {
      pushUnique("SS");
    } else if (ch === "c") {
      pushUnique(next === "e" || next === "i" || next === "y" ? "SS" : "KK");
    } else if (ch === "g") {
      pushUnique(next === "e" || next === "i" || next === "y" ? "CH" : "KK");
    } else if (ch === "j") {
      pushUnique("CH");
    } else if (ch === "k" || ch === "q") {
      pushUnique("KK");
    } else if (ch === "t" || ch === "d" || ch === "l") {
      pushUnique("DD");
    } else if (ch === "n") {
      pushUnique("NN");
    } else if (ch === "r") {
      pushUnique("RR");
    } else if (ch === "w") {
      pushUnique("U");
    } else if (ch === "x") {
      pushUnique("KK");
      pushUnique("SS");
    } else if (ch === "y") {
      pushUnique("I");
    } else if (ch === "a") {
      if (hasSilentE && i === chars.length - 2) {
        pushUnique("E");
        pushUnique("I");
      } else {
        pushUnique("AA");
      }
    } else if (ch === "e") {
      pushUnique("E");
    } else if (ch === "i") {
      if (hasSilentE && i === chars.length - 2) {
        pushUnique("AA");
        pushUnique("I");
      } else {
        pushUnique("I");
      }
    } else if (ch === "o") {
      pushUnique("O");
    } else if (ch === "u") {
      pushUnique(hasSilentE && i === chars.length - 2 ? "U" : "AA");
    } else if (ch === "h") {
      // Soft breathy onset before vowel
      if (out.length === 0) pushUnique("AA");
    }

    i += 1;
  }

  return out.length > 0 ? out : ["AA"];
}

/**
 * Expand timed word boundaries into a smooth phoneme-viseme frame timeline.
 */
export function buildPhonemeTimeline(wordTimings: WordTiming[]): PhonemeFrame[] {
  const frames: PhonemeFrame[] = [];
  if (!wordTimings || wordTimings.length === 0) return frames;

  for (const wt of wordTimings) {
    const tokens = wordToPhonemes(wt.word);
    if (tokens.length === 0) continue;

    const totalDur = Math.max(45, wt.duration_ms);
    const weights = tokens.map((tok) => PHONEME_POSES[tok]?.weight ?? 1.0);
    const weightSum = weights.reduce((a, b) => a + b, 0) || 1;

    let cursor = wt.offset_ms;
    for (let idx = 0; idx < tokens.length; idx++) {
      const tok = tokens[idx];
      const def = PHONEME_POSES[tok] ?? PHONEME_POSES.AA;
      const segDur = (totalDur * weights[idx]) / weightSum;
      frames.push({
        phoneme: tok,
        start_ms: cursor,
        end_ms: cursor + segDur,
        isBilabial: Boolean(def.bilabial),
        pose: def.pose,
      });
      cursor += segDur;
    }
  }

  return frames;
}

const ALL_VISEME_KEYS: VisemeKey[] = [
  "viseme_sil",
  "viseme_PP",
  "viseme_FF",
  "viseme_TH",
  "viseme_DD",
  "viseme_kk",
  "viseme_nn",
  "viseme_RR",
  "viseme_SS",
  "viseme_CH",
  "viseme_aa",
  "viseme_E",
  "viseme_I",
  "viseme_O",
  "viseme_U",
  "jawOpen",
  "mouthClose",
  "mouthPressLeft",
  "mouthPressRight",
  "mouthPucker",
  "mouthFunnel",
  "mouthRollLower",
  "mouthStretchLeft",
  "mouthStretchRight",
];

/**
 * Sample coarticulated viseme pose weights at audio time `timeMs`.
 * Blends adjacent phonemes smoothly with 35ms anticipatory overlap while preserving
 * strict lip closure on bilabial M/B/P sounds (`jawOpen -> 0`).
 */
export function sampleVisemeTimeline(
  frames: PhonemeFrame[],
  timeMs: number,
  acousticScale: number = 1.0
): { weights: Record<VisemeKey, number>; activePhoneme: string | null } {
  const weights = {} as Record<VisemeKey, number>;
  for (const k of ALL_VISEME_KEYS) {
    weights[k] = 0;
  }

  if (!frames || frames.length === 0) {
    weights.viseme_sil = 1.0;
    return { weights, activePhoneme: null };
  }

  const coartPadMs = 32;
  let totalContribution = 0;
  let dominantPhoneme: string | null = null;
  let dominantWeight = 0;
  let bilabialStrength = 0;

  for (let i = 0; i < frames.length; i++) {
    const f = frames[i];
    if (timeMs < f.start_ms - coartPadMs) break;
    if (timeMs > f.end_ms + coartPadMs) continue;

    // Smooth raised-cosine envelope across [start - pad, end + pad]
    const spanStart = f.start_ms - coartPadMs;
    const spanEnd = f.end_ms + coartPadMs;
    const center = (f.start_ms + f.end_ms) * 0.5;
    const halfDur = Math.max(18, (f.end_ms - f.start_ms) * 0.5);
    const dist = Math.abs(timeMs - center);

    let w = 0;
    if (timeMs >= f.start_ms && timeMs <= f.end_ms) {
      // Inside active phoneme core: high strength (0.75..1.0)
      const normDist = dist / halfDur;
      w = 0.78 + 0.22 * Math.cos(normDist * Math.PI * 0.5);
    } else if (timeMs >= spanStart && timeMs <= spanEnd) {
      // Anticipatory/trailing coarticulation skirt
      const edgeDist = timeMs < f.start_ms ? f.start_ms - timeMs : timeMs - f.end_ms;
      w = 0.5 * (1 + Math.cos((edgeDist / coartPadMs) * Math.PI)) * 0.45;
    }

    if (w > 0.01) {
      totalContribution += w;
      if (w > dominantWeight) {
        dominantWeight = w;
        dominantPhoneme = f.phoneme;
      }
      if (f.isBilabial) {
        bilabialStrength = Math.max(bilabialStrength, w);
      }
      for (const [key, val] of Object.entries(f.pose)) {
        const k = key as VisemeKey;
        weights[k] += (val || 0) * w;
      }
    }
  }

  if (totalContribution <= 0.01) {
    weights.viseme_sil = 1.0;
    return { weights, activePhoneme: null };
  }

  // Normalize blended phoneme overlap if > 1.0 so poses never stack excessively
  if (totalContribution > 1.0) {
    for (const k of ALL_VISEME_KEYS) {
      weights[k] /= totalContribution;
    }
  }

  // Apply subtle acoustic syllable stress scaling (keeping bilabial closure crisp)
  const clampedScale = Math.max(0.65, Math.min(1.25, acousticScale));
  for (const k of ALL_VISEME_KEYS) {
    if (k !== "viseme_sil") {
      weights[k] = Math.min(0.95, weights[k] * clampedScale);
    }
  }

  // Enforce strict lip seal during M / B / P bilabials so jaw never hangs open on closed consonants
  if (bilabialStrength > 0.35) {
    const sealFactor = Math.max(0, 1.0 - bilabialStrength * 1.15);
    weights.jawOpen *= sealFactor;
    weights.viseme_aa *= sealFactor;
    weights.viseme_O *= sealFactor;
  }

  weights.viseme_sil = Math.max(0, 1.0 - Math.min(1.0, totalContribution));
  return { weights, activePhoneme: dominantPhoneme };
}
