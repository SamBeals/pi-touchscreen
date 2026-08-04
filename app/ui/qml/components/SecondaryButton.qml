import QtQuick

PrimaryButton {
    secondary: true
    implicitHeight: Math.max(Theme.secondaryButtonMinHeight, implicitContentHeight + 20)
}
