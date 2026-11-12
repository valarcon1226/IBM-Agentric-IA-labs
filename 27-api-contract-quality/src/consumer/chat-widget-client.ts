import axios, { AxiosInstance, AxiosResponse } from 'axios';

export interface WebChatRequest {
  session_id: string;
  text: string;
}

export interface WebChatResponse {
  replies: string[];
}

export interface WebChatErrorResponse {
  detail: unknown;
}

export class ChatWidgetClient {
  private client: AxiosInstance;

  constructor(baseUrl: string) {
    this.client = axios.create({
      baseURL: baseUrl,
      headers: {
        'Content-Type': 'application/json',
      },
      validateStatus: () => true, // Don't throw on error status codes
    });
  }

  async sendMessage(
    sessionId: string,
    text: string,
  ): Promise<AxiosResponse<WebChatResponse | WebChatErrorResponse>> {
    return this.client.post<WebChatResponse | WebChatErrorResponse>('/web/chat', {
      session_id: sessionId,
      text,
    });
  }
}
