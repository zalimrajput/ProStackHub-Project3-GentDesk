"use client";

import ReactMarkdown from "react-markdown";

export function ReportView({ content }: { content: string }) {
  return (
    <article
      className="prose prose-invert prose-sm max-w-none
        prose-headings:font-semibold prose-headings:tracking-tight
        prose-headings:mt-8 prose-headings:first:mt-0
        prose-h1:text-2xl prose-h1:text-white
        prose-h2:border-b prose-h2:border-white/10 prose-h2:pb-2 prose-h2:text-lg prose-h2:text-indigo-200
        prose-h3:text-base prose-h3:text-fuchsia-200
        prose-p:leading-relaxed prose-p:text-slate-300
        prose-strong:text-white
        prose-a:text-indigo-300 prose-a:no-underline hover:prose-a:underline
        prose-code:rounded prose-code:bg-white/10 prose-code:px-1 prose-code:py-0.5 prose-code:font-normal prose-code:text-rose-300 prose-code:before:content-[''] prose-code:after:content-['']
        prose-pre:border prose-pre:border-white/10 prose-pre:bg-black/40 prose-pre:rounded-xl
        prose-blockquote:border-l-indigo-400/60 prose-blockquote:bg-indigo-500/5 prose-blockquote:py-0.5 prose-blockquote:not-italic prose-blockquote:text-slate-300
        prose-li:text-slate-300
        prose-li:marker:text-indigo-400
        prose-table:text-xs
        prose-th:text-slate-400 prose-th:uppercase prose-th:tracking-wider
        prose-td:border-white/10 prose-th:border-white/10
        prose-hr:border-white/10"
    >
      <ReactMarkdown>{content}</ReactMarkdown>
    </article>
  );
}
