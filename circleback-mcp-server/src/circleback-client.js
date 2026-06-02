import axios from 'axios';

export class CirclebackClient {
  constructor() {
    this.baseURL = 'https://api.circleback.ai/v2';
    this.token = null;
  }

  setToken(token) {
    this.token = token;
  }

  async request(method, endpoint, data = null) {
    try {
      const config = {
        method,
        url: `${this.baseURL}${endpoint}`,
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json',
          'User-Agent': 'Circleback-MCP-Server/1.0'
        }
      };

      if (data) {
        config.data = data;
      }

      const response = await axios(config);
      return response.data;
    } catch (error) {
      throw new Error(
        `Circleback API Error: ${error.response?.status} - ${error.response?.data?.message || error.message}`
      );
    }
  }

  // ========== MEETINGS ==========
  async searchMeetings(query, options = {}) {
    const params = new URLSearchParams({
      q: query,
      limit: options.limit || 10,
      offset: options.offset || 0,
      ...(options.tag && { tag: options.tag }),
      ...(options.attendee && { attendee: options.attendee }),
      ...(options.startDate && { startDate: options.startDate }),
      ...(options.endDate && { endDate: options.endDate })
    });

    return this.request('GET', `/meetings/search?${params}`);
  }

  async getMeeting(meetingId) {
    return this.request('GET', `/meetings/${meetingId}`);
  }

  async listMeetings(options = {}) {
    const params = new URLSearchParams({
      limit: options.limit || 20,
      offset: options.offset || 0
    });
    return this.request('GET', `/meetings?${params}`);
  }

  // ========== TRANSCRIPTS ==========
  async searchTranscripts(query, options = {}) {
    return this.request('POST', '/transcripts/search', {
      query,
      limit: options.limit || 10,
      meetingId: options.meetingId
    });
  }

  async getTranscript(meetingId) {
    return this.request('GET', `/meetings/${meetingId}/transcript`);
  }

  // ========== ACTION ITEMS ==========
  async searchActionItems(query, options = {}) {
    const params = new URLSearchParams({
      q: query,
      status: options.status || 'all',
      limit: options.limit || 10
    });
    return this.request('GET', `/action-items/search?${params}`);
  }

  async getActionItem(itemId) {
    return this.request('GET', `/action-items/${itemId}`);
  }

  // ========== EMAILS ==========
  async searchEmails(query, options = {}) {
    return this.request('POST', '/emails/search', {
      query,
      sender: options.sender,
      recipient: options.recipient,
      limit: options.limit || 10
    });
  }

  // ========== PROFILES ==========
  async findProfile(name) {
    const params = new URLSearchParams({ name });
    return this.request('GET', `/profiles/search?${params}`);
  }

  async getProfile(profileId) {
    return this.request('GET', `/profiles/${profileId}`);
  }

  // ========== CALENDAR ==========
  async searchCalendarEvents(options = {}) {
    const params = new URLSearchParams({
      limit: options.limit || 10,
      ...(options.startDate && { startDate: options.startDate }),
      ...(options.endDate && { endDate: options.endDate })
    });
    return this.request('GET', `/calendar/events?${params}`);
  }
}
