from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

# standard base for sqlalchemy models
Base = declarative_base()

class Alert(Base):
    # This table stores every alert we generate
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    direction = Column(String)  # UP or DOWN basically
    change_pct = Column(Float)
    beta = Column(Float)
    message = Column(String)

    def to_dict(self):
        # helper to convert the object to a dictionary for the api
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction,
            "change_pct": self.change_pct,
            "beta": self.beta,
            "message": self.message
        }
