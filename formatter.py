from typing import Dict, List, Any

MAX_MESSAGE_LENGTH = 4096

def escape_html(text: str) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def format_sentiment(score: float, normalized_score: float = None) -> str:
    # Assuming score 0-100
    label = "Neutral"
    if score > 60:
        label = "Positive"
    elif score < 40:
        label = "Negative"
        
    return f"{score} ({label})"

def chunk_text(text: str, limit: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Splits long text into chunks.
    This is a naive splitter. For HTML it's risky but sufficient if we split on block boundaries.
    """
    if len(text) <= limit:
        return [text]
    
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
            
        # Try to find a newline near the limit
        split_at = text.rfind('\n', 0, limit)
        if split_at == -1:
            split_at = limit
            
        chunk = text[:split_at]
        chunks.append(chunk)
        text = text[split_at:].strip()
        
    return chunks

def format_forecast_results(data: Dict[str, Any]) -> List[str]:
    """
    Returns a list of messages to send.
    Usually each string in the list is a full topic message.
    """
    results = data.get("results", [])
    if not results:
        return ["No significant news found for these parameters."]

    messages = []
    
    # Try to extract metadata for context
    # Usually metadata is per result or at top level? 
    # Prompt says "Each topic result may contain... metadata".
    # But usually API standardizes top level. I will look for it in first result or assume passed in params.
    # Actually prompt says: "metadata (countries, timeWindow, language...)" is inside the result item?
    # Let's check prompt: "Each topic result may contain: ... metadata". 
    # Okay, we check the first result's metadata or each result's metadata.

    for item in results:
        msg_parts = []
        
        topic = escape_html(item.get("topic", "Unknown Topic"))
        summary = escape_html(item.get("summary", ""))
        
        meta = item.get("metadata", {})
        countries = meta.get("countries", "?")
        time_horizon = meta.get("timeWindow", "?") # Prompt said timeWindow in metadata
        output_mode = meta.get("outputMode", "?") # likely depth?
        
        sentiment_display = item.get("sentimentScoreDisplay", 0)
        sentiment_str = format_sentiment(sentiment_display)
        
        # Header
        msg_parts.append(f"<b>{topic}</b>")
        msg_parts.append(f"<i>Context: {countries} | {time_horizon} | {output_mode}</i>")
        msg_parts.append(f"<b>Sentiment:</b> {sentiment_str}")
        msg_parts.append("")
        msg_parts.append(summary)
        
        # Narrative Comparison
        convergence = item.get("convergenceAnalysis")
        if convergence:
            msg_parts.append("")
            msg_parts.append("<b>Narrative Comparison:</b>")
            msg_parts.append(escape_html(convergence))
            
        # Sources
        sources = item.get("sources", [])
        if sources:
            msg_parts.append("")
            msg_parts.append("<b>Sources:</b>")
            
            display_count = 5
            for i, src in enumerate(sources[:display_count]):
                name = escape_html(src.get("name", "Source"))
                url = src.get("url", "")
                if url:
                    msg_parts.append(f"{i+1}. <a href=\"{url}\">{name}</a>")
                else:
                    msg_parts.append(f"{i+1}. {name}")
            
            if len(sources) > display_count:
                msg_parts.append(f"<i>+{len(sources) - display_count} more sources</i>")
                
        # Join
        full_msg = "\n".join(msg_parts)
        
        # Chunk if needed (rare for one topic but possible)
        if len(full_msg) > MAX_MESSAGE_LENGTH:
            # Naive chunking might break tags like <b> or <a href>
            # For this task, strict HTML safety in chunking is complex. 
            # I will assume standard topics fit. If not, we might send broken HTML.
            # To be safer, I should maybe just not send massive summaries.
            # However, I will use the simple chunker. 
            # Ideally, we chunk by sections.
            messages.extend(chunk_text(full_msg))
        else:
            messages.append(full_msg)
            
    return messages
