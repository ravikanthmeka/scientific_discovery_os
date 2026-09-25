import React from 'react';
import { useParams, Link, Navigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { BLOG_POSTS } from './Blog';

const BlogPost = () => {
  const { id } = useParams();
  const post = BLOG_POSTS[id];

  if (!post) {
    return <Navigate to="/blog" />;
  }

  return (
    <div className="blog-post-content">
      <Link to="/blog" className="back-link">← Back to Blog Index</Link>
      <article>
        <h1>{post.title}</h1>
        <div className="blog-date" style={{ marginBottom: '2rem' }}>
          {new Date(post.date).toLocaleDateString()}
        </div>
        
        <div className="markdown-body">
          <ReactMarkdown>{post.content}</ReactMarkdown>
        </div>
      </article>
    </div>
  );
};

export default BlogPost;
