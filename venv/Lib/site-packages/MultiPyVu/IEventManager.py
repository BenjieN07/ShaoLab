"""
CommandEventManager.py has the base classes for the events
using the Observer design pattern.
"""

from abc import ABC, abstractmethod
from typing import List


class IObserver(ABC):
    @classmethod
    def __subclasshook__(cls, subclass):
        return (
            hasattr(subclass, 'update')
            and callable(subclass.update)
            or NotImplemented)

    @abstractmethod
    def update(self, *args) -> None:
        raise NotImplementedError


class Publisher():
    # class variables
    _observers: List[IObserver] = []

    def __init__(self):
        pass

    def subscribe(self, observer: IObserver) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer: IObserver) -> None:
        try:
            self._observers.remove(observer)
        except ValueError:
            pass

    def notify_observers(self, *args) -> None:
        for observer in self._observers:
            observer.update(*args)
