// EdgeFlow AI - fixed-size queue of SignalFaultEvents waiting for the MQTT link.
//
// A fault raised while the broker is unreachable (exactly when it matters most) is kept here and sent
// once the link is back, oldest first. When full, the oldest entry is dropped and counted so the next
// event sent reports how many were lost. No heap allocation: safe to use from the main loop forever.
#pragma once
#include <Arduino.h>

struct QueuedFault
{
  char category[16];
  char code[32];
  char severity[9];
  char reason[112];
  char target[32];
  char phase[24];
  char clearance[16];
  char details[160]; // small JSON object, merged into the event's "details"
  uint32_t occurredMs;
  uint32_t seq;
};

template <size_t N>
class FaultQueue
{
public:
  void push(const QueuedFault &f)
  {
    if (count_ == N)
    {
      head_ = (head_ + 1) % N;
      count_--;
      dropped_++;
    }
    items_[(head_ + count_) % N] = f;
    count_++;
  }
  bool empty() const { return count_ == 0; }
  size_t size() const { return count_; }
  const QueuedFault &front() const { return items_[head_]; }
  void pop()
  {
    if (count_ == 0)
      return;
    head_ = (head_ + 1) % N;
    count_--;
  }
  uint32_t takeDropped()
  {
    uint32_t d = dropped_;
    dropped_ = 0;
    return d;
  }

private:
  QueuedFault items_[N];
  size_t head_ = 0;
  size_t count_ = 0;
  uint32_t dropped_ = 0;
};

// strncpy that always terminates
inline void copyField(char *dst, size_t size, const char *src)
{
  if (size == 0)
    return;
  strncpy(dst, src ? src : "", size - 1);
  dst[size - 1] = '\0';
}
