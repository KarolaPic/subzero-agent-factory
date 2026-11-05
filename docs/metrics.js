/**
 * Metric calculation engine and run log parser for GitHub Pages Factory Dashboard.
 * Reads .factory/runs/runs.jsonl format and calculates lifecycle durations and rates.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.DashboardMetrics = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function parseTimestamp(ts) {
    if (!ts || typeof ts !== 'string') return null;
    const d = new Date(ts);
    return isNaN(d.getTime()) ? null : d.getTime();
  }

  function parseRunLog(rawText) {
    if (!rawText || typeof rawText !== 'string' || !rawText.trim()) return [];
    const lines = rawText.trim().split('\n');
    const records = [];
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const record = JSON.parse(trimmed);
        if (record && typeof record === 'object') {
          records.push(record);
        }
      } catch (e) {
        // Skip malformed lines gracefully
      }
    }
    return records;
  }

  function getInterventionCount(humanIntervened) {
    if (typeof humanIntervened === 'boolean') {
      return humanIntervened ? 1 : 0;
    }
    if (humanIntervened && typeof humanIntervened === 'object') {
      if (typeof humanIntervened.count === 'number') {
        return Math.max(0, humanIntervened.count);
      }
      return humanIntervened.occurred ? 1 : 0;
    }
    return 0;
  }

  function computeMetrics(records) {
    if (!Array.isArray(records) || records.length === 0) {
      return {
        totalRuns: 0,
        prsOpened: 0,
        prsMerged: 0,
        avgKickoffToPrSeconds: 0,
        avgPrToReviewSeconds: 0,
        avgReviewToMergeSeconds: 0,
        totalInterventions: 0,
        interventionsPerPr: 0,
        runs: []
      };
    }

    let prsOpened = 0;
    let prsMerged = 0;
    let totalInterventions = 0;

    let totalKickoffToPrMs = 0;
    let countKickoffToPr = 0;

    let totalPrToReviewMs = 0;
    let countPrToReview = 0;

    let totalReviewToMergeMs = 0;
    let countReviewToMerge = 0;

    const processedRuns = records.map(function (r) {
      const kickoff = parseTimestamp(r.kickoff_at);
      const prOpened = parseTimestamp(r.pr_opened_at);
      const firstReview = parseTimestamp(r.first_review_at);
      const merged = parseTimestamp(r.merged_at);

      const hasPr = r.pr !== null && r.pr !== undefined && r.pr !== '';
      const isMerged = r.result === 'merged' || merged !== null;

      if (hasPr || prOpened !== null) {
        prsOpened++;
      }
      if (isMerged) {
        prsMerged++;
      }

      const interventions = getInterventionCount(r.human_intervened);
      totalInterventions += interventions;

      let kickoffToPrSec = null;
      if (kickoff !== null && prOpened !== null && prOpened >= kickoff) {
        const diffMs = prOpened - kickoff;
        kickoffToPrSec = Math.round(diffMs / 1000);
        totalKickoffToPrMs += diffMs;
        countKickoffToPr++;
      }

      let prToReviewSec = null;
      if (prOpened !== null && firstReview !== null && firstReview >= prOpened) {
        const diffMs = firstReview - prOpened;
        prToReviewSec = Math.round(diffMs / 1000);
        totalPrToReviewMs += diffMs;
        countPrToReview++;
      }

      let reviewToMergeSec = null;
      if (firstReview !== null && merged !== null && merged >= firstReview) {
        const diffMs = merged - firstReview;
        reviewToMergeSec = Math.round(diffMs / 1000);
        totalReviewToMergeMs += diffMs;
        countReviewToMerge++;
      }

      return {
        issue: r.issue,
        pr: r.pr,
        result: r.result || 'unknown',
        builder: r.builder || 'unknown',
        auditor: r.auditor || 'unknown',
        prScore: r.pr_score !== undefined ? r.pr_score : null,
        interventions: interventions,
        kickoffToPrSec: kickoffToPrSec,
        prToReviewSec: prToReviewSec,
        reviewToMergeSec: reviewToMergeSec
      };
    });

    return {
      totalRuns: records.length,
      prsOpened: prsOpened,
      prsMerged: prsMerged,
      avgKickoffToPrSeconds: countKickoffToPr > 0 ? Math.round((totalKickoffToPrMs / countKickoffToPr) / 1000) : 0,
      avgPrToReviewSeconds: countPrToReview > 0 ? Math.round((totalPrToReviewMs / countPrToReview) / 1000) : 0,
      avgReviewToMergeSeconds: countReviewToMerge > 0 ? Math.round((totalReviewToMergeMs / countReviewToMerge) / 1000) : 0,
      totalInterventions: totalInterventions,
      interventionsPerPr: prsOpened > 0 ? Number((totalInterventions / prsOpened).toFixed(2)) : 0,
      runs: processedRuns
    };
  }

  function formatDuration(seconds) {
    if (seconds === null || seconds === undefined || isNaN(seconds) || seconds <= 0) {
      return '0s';
    }
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins > 0) {
      return mins + 'm ' + secs + 's';
    }
    return secs + 's';
  }

  return {
    parseRunLog: parseRunLog,
    computeMetrics: computeMetrics,
    getInterventionCount: getInterventionCount,
    formatDuration: formatDuration
  };
});
