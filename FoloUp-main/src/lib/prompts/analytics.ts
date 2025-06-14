export const SYSTEM_PROMPT =
  "You are an expert in analyzing interview transcripts. You must only use the main questions provided and not generate or infer additional questions.";

export const getInterviewAnalyticsPrompt = (
  interviewTranscript: string,
  mainInterviewQuestions: string,
) => `Analyse the following interview transcript and provide structured feedback:

###
Transcript: ${interviewTranscript}

Main Interview Questions:
${mainInterviewQuestions}


Based on this transcript and the provided main interview questions, generate the following analytics in JSON format:
1. Overall Score (0-100) and Overall Feedback (60 words) - take into account the following factors:
   - Communication Skills: Evaluate the use of language, grammar, and vocabulary. Assess if the interviewee communicated effectively and clearly.
   - Time Taken to Answer: Consider if the interviewee answered promptly or took too long. Note if they were concise or tended to ramble.
   - Confidence: Assess the interviewee's confidence level. Were they assertive and self-assured, or did they seem hesitant and unsure?
   - Clarity: Evaluate the clarity of their answers. Were their responses well-structured and easy to understand?
   - Attitude: Consider the interviewee's attitude towards the interview and questions. Were they positive, respectful, and engaged?
   - Relevance of Answers: Determine if the interviewee's responses are relevant to the questions asked. Assess if they stayed on topic or veered off track.
   - Depth of Knowledge: Evaluate the interviewee's depth of understanding and knowledge in the subject matter. Look for detailed and insightful answers.
   - Problem-Solving Ability: Consider how the interviewee approaches problem-solving questions. Assess their logical reasoning and analytical skills.
   - Examples and Evidence: Note if the interviewee provides concrete examples or evidence to support their answers. This can indicate experience and credibility.
   - Listening Skills: Look for signs that the interviewee is actively listening and responding appropriately to follow-up questions.
   - Consistency: Evaluate if the interviewee's answers are consistent throughout the interview or if they contradict themselves.
   - Adaptability: Assess how well the interviewee adapts to different types of questions, including unexpected or challenging ones.

2. Communication Skills: Score (0-10) and Feedback (60 words). Rating system and guidleines for communication skills is as follwing.
    - 10: Fully operational command, use of English is appropriate, accurate, fluent, shows complete understanding.
    - 09: Fully operational command with occasional inaccuracies and inappropriate usage. May misunderstand unfamiliar situations but handles complex arguments well.
    - 08: Operational command with occasional inaccuracies, inappropriate usage, and misunderstandings. Handles complex language and detailed reasoning well.
    - 07: Effective command despite some inaccuracies, inappropriate usage, and misunderstandings. Can use and understand reasonably complex language, especially in familiar situations.
    - 06: Partial command, copes with overall meaning, frequent mistakes. Handles basic communication in their field.
    - 05: Basic competence limited to familiar situations with frequent problems in understanding and expression.
    - 04: Understands only general meaning in very familiar situations, with frequent communication breakdowns.
    - 03: Has great difficulty understanding spoken English.
    - 02: Has no ability to use the language except a few isolated words.
    - 01: Did not answer the questions.
3. Summary for each main interview question: ${mainInterviewQuestions}
   - Use ONLY the main questions provided, it should output all the questions with the numbers even if it's not found in the transcript.
   - Follow the below rules when outputing the question and summary
      - If a main interview question isn't found in the transcript, then output the main question and give the summary as "Not Asked"
      - If a main interview question is found in the transcript but an answer couldn't be found, then output the main question and give the summary as "Not Answered"
      - If a main interview question is found in the transcript and an answer can also be found, then,
          - For each main question (q), provide a summary that includes:
            a) The candidate's response to the main question
            b) Any follow-up questions that were asked related to this main question and their answers
          - The summary should be a cohesive paragraph encompassing all related information for each main question
4. Create a 10 to 15 words summary regarding the soft skills considering factors such as confidence, leadership, adaptability, critical thinking and decision making.
Ensure the output is in valid JSON format with the following structure:
{
  "overallScore": number,
  "overallFeedback": string,
  "communication": { "score": number, "feedback": string },
  "questionSummaries": [{ "question": string, "summary": string }],
  "softSkillSummary: string
}

IMPORTANT: Only use the main questions provided. Do not generate or infer additional questions such as follow-up questions.`;
