import path from 'path';
import { PactV3, MatchersV3 } from '@pact-foundation/pact';
import { ChatWidgetClient, WebChatResponse } from '../../src/consumer/chat-widget-client';

const { string, eachLike } = MatchersV3;

const provider = new PactV3({
  consumer: 'WebChatWidget',
  provider: 'RestaurantAssistantAPI',
  dir: path.resolve(process.cwd(), 'pacts'),
});

describe('WebChatWidget Consumer Contract Tests', () => {
  describe('when a customer sends a message via the chat widget', () => {
    it('receives an array of assistant replies (200 OK)', async () => {
      provider
        .given('the assistant is available')
        .uponReceiving('a valid chat message from web widget')
        .withRequest({
          method: 'POST',
          path: '/web/chat',
          headers: {
            'Content-Type': 'application/json',
          },
          body: {
            session_id: string('test-session-123'),
            text: string('¿Cuál es el horario de atención hoy?'),
          },
        })
        .willRespondWith({
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
          body: {
            replies: eachLike('¡Hola! Dime en qué te ayudo.'),
          },
        });

      await provider.executeTest(async (mockServer) => {
        const client = new ChatWidgetClient(mockServer.url);
        const res = await client.sendMessage(
          'test-session-123',
          '¿Cuál es el horario de atención hoy?',
        );

        expect(res.status).toBe(200);
        const data = res.data as WebChatResponse;
        expect(Array.isArray(data.replies)).toBe(true);
        expect(data.replies.length).toBeGreaterThanOrEqual(1);
        expect(typeof data.replies[0]).toBe('string');
      });
    });

    it('receives 422 Unprocessable Entity when message text is empty', async () => {
      provider
        .given('the assistant is available')
        .uponReceiving('a chat message with empty text')
        .withRequest({
          method: 'POST',
          path: '/web/chat',
          headers: {
            'Content-Type': 'application/json',
          },
          body: {
            session_id: string('test-session-123'),
            text: '',
          },
        })
        .willRespondWith({
          status: 422,
          headers: {
            'Content-Type': 'application/json',
          },
          body: {
            detail: eachLike({
              type: string('string_too_short'),
              loc: eachLike('body'),
              msg: string('String should have at least 1 character'),
            }),
          },
        });

      await provider.executeTest(async (mockServer) => {
        const client = new ChatWidgetClient(mockServer.url);
        const res = await client.sendMessage('test-session-123', '');

        expect(res.status).toBe(422);
        expect(res.data).toHaveProperty('detail');
      });
    });

    it('receives 429 Too Many Requests when rate limit is exceeded', async () => {
      provider
        .given('rate limit is exceeded for session')
        .uponReceiving('a chat message exceeding rate limit')
        .withRequest({
          method: 'POST',
          path: '/web/chat',
          headers: {
            'Content-Type': 'application/json',
          },
          body: {
            session_id: 'flood_999',
            text: string('Spam message'),
          },
        })
        .willRespondWith({
          status: 429,
          headers: {
            'Content-Type': 'application/json',
          },
          body: {
            detail: string('Límite de mensajes por minuto excedido.'),
          },
        });

      await provider.executeTest(async (mockServer) => {
        const client = new ChatWidgetClient(mockServer.url);
        const res = await client.sendMessage('flood_999', 'Spam message');

        expect(res.status).toBe(429);
        expect(res.data).toHaveProperty('detail', 'Límite de mensajes por minuto excedido.');
      });
    });
  });
});
