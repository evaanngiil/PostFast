import { useState } from "react";

interface UseHistoryDeps {
  authToken: string;
  orgUrn: string | undefined;
}

/** Dominio del historial de publicaciones (programadas / publicadas / borradores). */
export function useHistory({ authToken, orgUrn }: UseHistoryDeps) {
  const [postsHistory, setPostsHistory] = useState<any[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);

  const loadHistory = async (overrideUrn?: string) => {
    setIsLoadingHistory(true);
    try {
      const urn = overrideUrn || orgUrn;
      const url = urn
        ? `http://localhost:8000/content/posts?account_id=${encodeURIComponent(urn)}`
        : "http://localhost:8000/content/posts";

      const res = await fetch(url, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      const data = await res.json();
      if (Array.isArray(data)) {
        const seenContents = new Set<string>();
        const uniquePosts = data.filter((post: any) => {
          if (!post.content) return true;
          const normalized = post.content.trim();
          if (seenContents.has(normalized)) {
            return false;
          }
          seenContents.add(normalized);
          return true;
        });
        setPostsHistory(uniquePosts);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  return { postsHistory, setPostsHistory, isLoadingHistory, loadHistory };
}
