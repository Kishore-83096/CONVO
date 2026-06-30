import type { ReactNode } from "react";

type MainContentProps = {
    children: ReactNode;
};

export function MainContent({
    children,
}: MainContentProps) {
    return (
        <main className="conversation">
            {children}
        </main>
    );
}