import React from 'react';
import { Link } from 'react-router-dom';

export const BLOG_POSTS = {
  'how-to-use-ai-for-systematic-reviews': {
    title: 'How to use AI for Systematic Literature Reviews',
    date: '2026-08-30',
    content: `
A systematic review aims to synthesize all empirical evidence that fits pre-specified eligibility criteria in order to answer a specific research question. Traditionally, this process is painstakingly manual:

1. Formulate a question
2. Search databases (PubMed, OpenAlex)
3. Screen titles and abstracts
4. Extract data
5. Synthesize findings

## Enter Agentic AI

With tools like SynaptoLab, researchers can now automate the tedious parts. The AI can autonomously construct complex Boolean queries, hit the PubMed API, and parse thousands of abstracts in seconds. 

By defining your inclusion/exclusion criteria as a prompt, the agent can perform the initial screening with high precision. While the final review must still be human-verified, the time saved is measured in weeks, not hours.
    `,
    excerpt: 'Conducting a systematic review usually takes months of manual searching across PubMed and OpenAlex. See how agentic AI can reduce this to minutes.'
  },
  'hypothesis-generation-with-llms': {
    title: 'Hypothesis Generation using Large Language Models',
    date: '2026-08-15',
    content: `
Large Language Models (LLMs) are exceptional at pattern recognition across vast corpuses of text. This makes them uniquely suited for a novel task: **Hypothesis Generation**.

By feeding an LLM the latest findings from disjointed fields—for example, a recent paper on metabolic pathways in yeast and a separate paper on neurological degradation in mice—the model can identify hidden correlations.

## Mapping the Gaps

The true power of AI in science isn't just summarizing what we already know. It's mapping the whitespace between existing papers to suggest what we *should* investigate next.
    `,
    excerpt: 'LLMs are great at summarizing, but can they actually generate novel hypotheses? We explore how mapping cross-disciplinary gaps reveals new pathways.'
  }
};

const Blog = () => {
  return (
    <div className="blog-container">
      <Link to="/" className="back-link">← Back to Home</Link>
      <h1>SynaptoLab Blog</h1>
      <div className="blog-posts">
        {Object.entries(BLOG_POSTS).map(([id, post]) => (
          <div key={id} className="blog-post-card">
            <h2>
              <Link to={`/blog/${id}`}>{post.title}</Link>
            </h2>
            <div className="blog-date">{new Date(post.date).toLocaleDateString()}</div>
            <p className="blog-excerpt">{post.excerpt}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Blog;
