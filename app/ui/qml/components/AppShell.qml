import QtQuick
import SellMate 1.0

Item {
    id: root
    anchors.fill: parent

    Rectangle {
        anchors.fill: parent
        color: Theme.background
        visible: Theme.backgroundType === "solid" || Theme.backgroundType === "gradient"
    }

    Rectangle {
        anchors.fill: parent
        visible: Theme.backgroundType === "gradient"
        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: Theme.backgroundStops.length > 0 ? Theme.backgroundStops[0] : Theme.background
            }
            GradientStop {
                position: 1.0
                color: Theme.backgroundStops.length > 1 ? Theme.backgroundStops[1] : Theme.background
            }
        }
        opacity: 0.35
    }

    Image {
        anchors.fill: parent
        visible: Theme.backgroundType === "image" && Theme.backgroundImageUrl.length > 0
        source: Theme.backgroundImageUrl
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
    }

    Rectangle {
        anchors.fill: parent
        visible: Theme.backgroundType === "image"
        color: Theme.scrim
    }

    default property alias content: body.data

    Item {
        id: body
        anchors.fill: parent
        anchors.leftMargin: Theme.pageMargin
        anchors.rightMargin: Theme.pageMargin
        anchors.topMargin: Theme.pageMargin + 4
        anchors.bottomMargin: Theme.pageMargin
    }
}
