import QtQuick
import QtQuick.Layouts
import SellMate 1.0

RowLayout {
    id: root
    spacing: Theme.gap
    property int quantity: 1

    signal decrement()
    signal increment()

    SecondaryButton {
        text: "−"
        Layout.preferredWidth: 88
        Layout.fillWidth: false
        onClicked: root.decrement()
    }
    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: Theme.secondaryButtonMinHeight
        radius: Theme.cornerRadius
        color: Theme.secondary

        Text {
            anchors.centerIn: parent
            text: root.quantity
            color: Theme.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.subtitleFontPx
            font.bold: true
        }
    }
    SecondaryButton {
        text: "+"
        Layout.preferredWidth: 88
        Layout.fillWidth: false
        onClicked: root.increment()
    }
}
