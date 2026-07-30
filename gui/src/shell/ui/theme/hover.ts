import type React from "react";

export const hoverBg = (enterBg: string, leaveBg: string) => ({
  onMouseEnter: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.background = enterBg;
  },
  onMouseLeave: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.background = leaveBg;
  },
});

export const hoverBorderColor = (enterBorder: string, leaveBorder: string) => ({
  onMouseEnter: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.borderColor = enterBorder;
  },
  onMouseLeave: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.borderColor = leaveBorder;
  },
});

export const hoverColor = (enterColor: string, leaveColor: string) => ({
  onMouseEnter: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.color = enterColor;
  },
  onMouseLeave: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.color = leaveColor;
  },
});

export const hoverBrightness = (brightnessPercent: number = 95) => ({
  onMouseEnter: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.filter = `brightness(${brightnessPercent / 100})`;
  },
  onMouseLeave: (mouseEvent: React.MouseEvent<HTMLElement>) => {
    mouseEvent.currentTarget.style.filter = "none";
  },
});

export const hoverIf = <T extends object>(condition: boolean, handlers: T): T | object =>
  condition ? handlers : {};
